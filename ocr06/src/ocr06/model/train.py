"""Fine-tuning LoRA do Chandra (BF16) com transformers + peft (ambiente .venv-gpu).

    python -m ocr06.model.train            # treino completo (config: model.train)
    python -m ocr06.model.train --pilot    # poucos passos, só para medir velocidade

Lê data/final/<dataset>/{train,val}.jsonl. O encoder de visão fica congelado; o LoRA
entra só nas camadas lineares do modelo de linguagem. A perda é calculada apenas na
resposta (a transcrição), não no prompt nem na imagem. A validação usa a perda em
`max_val` linhas a cada `eval_steps`, com parada antecipada e o melhor checkpoint salvo.
Saída: models/<run>/adapter/ (adaptador + processor) e models/<run>/treino.json.

Dois tipos de exemplo podem vir misturados no mesmo arquivo:
  linha   formato de mix.py ({id, source, image, text, messages}). Imagem com altura
          normalizada (preprocess.load_line) e peso 1 em todos os tokens da resposta.
  página  traz `spans` (mesmo vazio) e `w_default`. Imagem com o lado maior reduzido a
          `model.train.page_max_side` (preprocess.load_page, o mesmo da inferência de
          páginas), sem normalizar altura. Cada token da resposta recebe peso: o `w` do
          trecho (`spans`, em caracteres do texto do assistente) que ele toca (o menor, se
          tocar mais de um: máscara w=0 sempre vence), `w_default` fora dos trechos
          (impresso e layout) e 1 no fim de turno. Prompt e imagem continuam fora da perda.
Com páginas no lote, a perda é a entropia cruzada ponderada dividida pela soma dos pesos
do lote; um lote só de linhas segue o caminho de sempre do Trainer. Com
`model.train.curriculum`, a ordem do treino segue `level` crescente (embaralhado dentro de
cada nível); exemplos sem `level` (as linhas) são intercalados por igual ao longo da
sequência, como repetição do que o modelo já sabe, em vez de ficarem todos no começo.
"""
from __future__ import annotations

import argparse
import json
import random
import time
from collections import Counter, defaultdict

import torch
from ..preprocess import load_line, load_page
from . import ROOT, data_dir, final_dir, load_config, model_paths


def load_jsonl(path) -> list[dict]:
    return [json.loads(line) for line in open(path, encoding="utf-8")]


def is_page(row: dict) -> bool:
    """Exemplo de página inteira: traz `spans` (mesmo vazio) ou `w_default`."""
    return "spans" in row or "w_default" in row


def assistant_text(row: dict) -> str:
    c = row["messages"][-1]["content"]
    return c if isinstance(c, str) else "".join(x.get("text", "") for x in c if x.get("type") == "text")


def lora_target_regex(model, names: list[str]) -> str:
    """Regex de módulos-alvo: camadas Linear com esses nomes, fora do encoder de visão."""
    found = set()
    for full, mod in model.named_modules():
        leaf = full.rsplit(".", 1)[-1]
        if isinstance(mod, torch.nn.Linear) and leaf in names and "visual" not in full:
            found.add(leaf)
    missing = sorted(set(names) - found)
    if missing:
        print(f"  (nomes de LoRA não presentes neste modelo, ignorados: {missing})")
    if not found:
        raise SystemExit("nenhuma camada-alvo de LoRA encontrada; confira model.lora.target")
    print(f"  LoRA em: {sorted(found)}")
    return rf"^(?!.*visual).*\.({'|'.join(sorted(found))})$"


def token_weights(offsets: list[tuple[int, int]], n_content: int, shift: int,
                  spans: list[dict], w_default: float) -> list[float]:
    """Peso de cada token da resposta. `offsets` são as posições (início, fim) de cada token
    no trecho conteúdo + fim de turno; o conteúdo é o texto do assistente sem os espaços das
    pontas (o chat template faz `trim`), e `shift` é quanto o `trim` tirou do começo, para
    levar as posições de volta às de `spans`. Tokens depois do conteúdo (<|im_end|> e a
    quebra de linha) recebem 1, como nas linhas."""
    out = []
    for s, e in offsets:
        if s >= n_content:
            out.append(1.0)
            continue
        s, e = s + shift, e + shift
        hit = [sp["w"] for sp in spans if s < sp["end"] and e > sp["start"]]
        out.append(float(min(hit)) if hit else float(w_default))
    return out


class Collator:
    """Monta o lote e mascara (-100) tudo que não é a resposta do assistente. Com algum
    exemplo de página no lote, devolve também `loss_weights` (mesmo formato de `labels`)."""

    def __init__(self, processor, ddir, cfg):
        self.p = processor
        self.tok = processor.tokenizer
        self.ddir = ddir
        self.cfg = cfg
        self.page_max_side = cfg["model"]["train"].get("page_max_side", 2048)
        self.p.tokenizer.padding_side = "right"

    def _template(self, messages, generation_prompt: bool) -> str:
        return self.p.apply_chat_template(messages, tokenize=False,
                                          add_generation_prompt=generation_prompt,
                                          enable_thinking=False)

    def image(self, row):
        path = self.ddir / row["image"]
        return load_page(path, self.page_max_side) if is_page(row) else load_line(path, self.cfg)

    def _page_tail(self, row, full: str, ids, length: int):
        """Para uma página: (n_prompt, pesos dos tokens da resposta). Tokeniza só a resposta
        (com offsets) e confere que ela é exatamente o fim da sequência do lote; assim não
        é preciso processar a imagem de novo para contar os tokens do prompt."""
        prompt = self._template(row["messages"][:1], True)
        if not full.startswith(prompt):
            raise ValueError(f"{row['id']}: o prompt não é prefixo do texto completo")
        raw = assistant_text(row)
        content = raw.strip()
        tail = full[len(prompt):]
        if not tail.startswith(content):
            raise ValueError(f"{row['id']}: resposta fora do lugar esperado no chat template")
        enc = self.tok(tail, add_special_tokens=False, return_offsets_mapping=True)
        n_prompt = length - len(enc["input_ids"])
        if n_prompt <= 0 or ids[n_prompt:length].tolist() != enc["input_ids"]:
            raise ValueError(f"{row['id']}: a resposta tokenizada sozinha difere da do lote")
        w = token_weights(enc["offset_mapping"], len(content), len(raw) - len(raw.lstrip()),
                          row.get("spans") or [], row.get("w_default", 1.0))
        return n_prompt, w

    def __call__(self, rows: list[dict]) -> dict:
        images = [self.image(r) for r in rows]
        full = [self._template(r["messages"], False) for r in rows]
        batch = self.p(text=full, images=images, padding=True, return_tensors="pt")
        labels = batch["input_ids"].clone()
        weights = torch.zeros(labels.shape, dtype=torch.float32) if any(map(is_page, rows)) else None
        for i, (r, img) in enumerate(zip(rows, images)):
            length = int(batch["attention_mask"][i].sum())
            if is_page(r):
                n_prompt, w = self._page_tail(r, full[i], batch["input_ids"][i], length)
                weights[i, n_prompt:length] = torch.tensor(w)
            else:  # linhas: exatamente como no treino das linhas (lora_v0)
                prompt = self._template(r["messages"][:1], True)
                n_prompt = self.p(text=[prompt], images=[img], return_tensors="pt")["input_ids"].shape[1]
                if weights is not None:
                    weights[i, n_prompt:length] = 1.0
            labels[i, :n_prompt] = -100
        labels[batch["attention_mask"] == 0] = -100
        batch["labels"] = labels
        if weights is not None:
            weights[labels == -100] = 0.0
            batch["loss_weights"] = weights
        return batch


def curriculum_order(rows: list[dict], seed: int) -> list[int]:
    """Índices por `level` crescente, embaralhados dentro de cada nível; os sem `level`
    entram intercalados por igual ao longo da sequência."""
    rng = random.Random(seed)
    levels: dict[int, list[int]] = defaultdict(list)
    free = []
    for i, r in enumerate(rows):
        (levels[int(r["level"])] if r.get("level") is not None else free).append(i)
    ordered = []
    for lv in sorted(levels):
        idx = levels[lv]
        rng.shuffle(idx)
        ordered += idx
    rng.shuffle(free)
    n, m = len(ordered), len(free)
    keyed = [((k + 0.5) / n, 0, i) for k, i in enumerate(ordered)] + \
            [((j + 0.5) / m, 1, i) for j, i in enumerate(free)]
    return [i for *_, i in sorted(keyed)]


class CurriculumSampler(torch.utils.data.Sampler):
    """Ordem fixa do currículo. Pensado para 1 época; numa 2ª o currículo recomeça (com
    outro embaralhamento dentro dos níveis; o Trainer chama set_epoch). A ordem só depende
    da seed e da época, então retomar de um checkpoint (`--resume`) pula exatamente os
    lotes já vistos."""

    def __init__(self, rows: list[dict], seed: int):
        self.rows, self.seed, self.epoch = rows, seed, 0

    def set_epoch(self, epoch: int) -> None:
        self.epoch = epoch

    def __iter__(self):
        return iter(curriculum_order(self.rows, self.seed + self.epoch))

    def __len__(self) -> int:
        return len(self.rows)


def weighted_lm_loss(logits: torch.Tensor, labels: torch.Tensor, weights: torch.Tensor) -> torch.Tensor:
    """Entropia cruzada com peso por token, dividida pela soma dos pesos. `logits` cobre as
    últimas K posições da sequência (logits_to_keep = K); posição t prevê o token t+1."""
    k = logits.shape[1]
    tgt = labels[:, -k:][:, 1:]
    w = weights[:, -k:][:, 1:].to(torch.float32) * (tgt != -100)
    ce = torch.nn.functional.cross_entropy(
        logits[:, :-1].float().reshape(-1, logits.shape[-1]), tgt.reshape(-1),
        ignore_index=-100, reduction="none")
    w = w.reshape(-1)
    if NAME_BOOST > 0:
        # Nomes (peso >= 2) apanham mais quando o modelo erra: o peso cresce com a
        # probabilidade que ele NÃO deu à letra certa (1 - p). Acertando com confiança, fica 2x;
        # errando feio, até 2x * (1 + NAME_BOOST). Fator sem gradiente, só reescala.
        p_ok = torch.exp(-ce.detach())
        w = torch.where(w >= 2.0, w * (1 + NAME_BOOST * (1 - p_ok)), w)
    return (ce * w).sum() / w.sum().clamp_min(1e-8)


NAME_BOOST = 0.0  # model.train.name_boost


def make_trainer(curriculum: bool, seed: int, train_rows: list[dict], **kw):
    """Trainer com a perda ponderada das páginas e, se pedido, o sampler do currículo.
    O Qwen3.5 tem accepts_loss_kwargs = False: o Trainer tira a média da perda de cada lote
    e divide pelos passos de acumulação; a perda ponderada segue a mesma convenção."""
    from transformers import Trainer

    class WeightedTrainer(Trainer):
        def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
            if "loss_weights" not in inputs:  # lote só de linhas: caminho padrão, igual ao lora_v0
                return super().compute_loss(model, inputs, return_outputs, num_items_in_batch)
            inputs = dict(inputs)
            weights, labels = inputs.pop("loss_weights"), inputs.pop("labels")
            # logits só a partir do 1º alvo do lote: imagem + prompt de uma página passam de
            # 3 mil tokens, e o lm_head (vocabulário de 248 mil) em fp32 seria o pico de memória
            cols = (labels != -100).any(0).nonzero()
            first = int(cols[0]) if len(cols) else labels.shape[1] - 1
            keep = min(labels.shape[1] - first + 1, labels.shape[1])
            outputs = model(**inputs, logits_to_keep=keep)
            loss = weighted_lm_loss(outputs.logits, labels, weights)
            return (loss, outputs) if return_outputs else loss

        def _get_train_sampler(self, train_dataset=None):
            if curriculum:
                return CurriculumSampler(train_rows, seed)
            return super()._get_train_sampler(train_dataset)

    return WeightedTrainer(train_dataset=train_rows, **kw)


def describe_target(processor, batch, i: int = 0, max_chars: int = 600) -> str:
    """O que o modelo aprende no exemplo i: os tokens de peso 1 (ou todo o alvo, se não há
    pesos), para conferir a máscara do prompt e o alinhamento dos trechos."""
    lab = batch["labels"][i]
    if "loss_weights" not in batch:
        return repr(processor.tokenizer.decode(lab[lab != -100]))
    w = batch["loss_weights"][i]
    hi = processor.tokenizer.decode(batch["input_ids"][i][w >= 1.0])
    cnt = Counter(round(float(x), 2) for x in w[lab != -100])
    return f"pesos {dict(sorted(cnt.items()))}; tokens de peso 1: {hi[:max_chars]!r}"


def main() -> None:
    from peft import LoraConfig, get_peft_model
    from transformers import (AutoModelForImageTextToText, AutoProcessor, EarlyStoppingCallback,
                              TrainingArguments)

    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--pilot", action="store_true", help="poucos passos para medir velocidade")
    ap.add_argument("--max-steps", type=int, help="limite de passos (orçamento medido no piloto)")
    ap.add_argument("--resume", action="store_true",
                    help="continua do último checkpoint deste run (após queda da sessão)")
    args = ap.parse_args()
    cfg = load_config(args.config)
    mc, tc, lc = cfg["model"], cfg["model"]["train"], cfg["model"]["lora"]
    global NAME_BOOST
    NAME_BOOST = float(tc.get("name_boost", 0.0))
    paths = model_paths(cfg)
    paths["run"].mkdir(parents=True, exist_ok=True)
    rng = random.Random(cfg["seed"])

    train_rows = load_jsonl(final_dir(cfg) / "train.jsonl")
    val_all = load_jsonl(final_dir(cfg) / "val.jsonl")
    val_sets = {}
    for src, n in tc["max_val"].items():
        rows = [r for r in val_all if r["source"] == src]
        if not rows:
            print(f"  (sem exemplos de validação com source={src}; conjunto ignorado)")
            continue
        val_sets[src] = rng.sample(rows, n) if len(rows) > n else rows
    n_pages = sum(map(is_page, train_rows))
    curriculum = bool(tc.get("curriculum", False))
    print(f"== treino: {len(train_rows)} exemplos ({n_pages} páginas, {len(train_rows) - n_pages} linhas) "
          f"| validação: " + ", ".join(f"{k} {len(v)}" for k, v in val_sets.items()))
    if curriculum:
        lv = Counter(r.get("level") for r in train_rows)
        print(f"  currículo por nível: {dict(sorted(lv.items(), key=lambda x: (x[0] is None, x[0] or 0)))}"
              " (None = intercalados)")
        if tc["epochs"] != 1:
            print("  aviso: o currículo é pensado para 1 época; em cada época ele recomeça do nível 1")

    processor = AutoProcessor.from_pretrained(mc["base"], trust_remote_code=True)
    # Mesmos limites de pixels da inferência (model.vllm), para o modelo ver as linhas na
    # mesma escala no treino e no teste.
    processor.image_processor.size = {"shortest_edge": mc["vllm"]["min_pixels"],
                                      "longest_edge": mc["vllm"]["max_pixels"]}
    model = AutoModelForImageTextToText.from_pretrained(
        mc["base"], dtype=torch.bfloat16, trust_remote_code=True, attn_implementation="sdpa")
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.enable_input_require_grads()
    if tc.get("init_adapter"):  # 2ª etapa: continua um adaptador já treinado
        from peft import PeftModel
        print(f"  continuando o adaptador {tc['init_adapter']}")
        model = PeftModel.from_pretrained(model, str(ROOT / tc["init_adapter"]), is_trainable=True)
    else:
        model = get_peft_model(model, LoraConfig(
            r=lc["r"], lora_alpha=lc["alpha"], lora_dropout=lc["dropout"],
            target_modules=lora_target_regex(model, lc["target"]), bias="none"))
    model.print_trainable_parameters()

    collator = Collator(processor, data_dir(cfg), cfg)
    # Mostra o que o modelo vai aprender no 1º exemplo (confere a máscara do prompt) e, se
    # houver, no 1º exemplo de página (confere os pesos dos trechos).
    shown = [train_rows[0]]
    page = next((r for r in train_rows if is_page(r)), None)
    if page is not None and page is not train_rows[0]:
        shown.append(page)
    for row in shown:
        b = collator([row])
        esperado = row.get("text", "") if not is_page(row) else f"{len(row.get('spans', []))} trechos"
        print(f"  alvo de {row['id']}: {describe_target(processor, b)}  (esperado: {esperado!r} + fim de turno)")

    pilot = args.pilot
    targs = TrainingArguments(
        output_dir=str(paths["checkpoints"]),
        per_device_train_batch_size=tc["batch_size"],
        per_device_eval_batch_size=tc["batch_size"],
        gradient_accumulation_steps=tc["grad_accum"],
        learning_rate=tc["lr"],
        num_train_epochs=tc["epochs"],
        max_steps=tc["pilot_steps"] if pilot else (args.max_steps or -1),
        warmup_steps=tc["warmup_ratio"],  # < 1 = fração dos passos (warmup_ratio saiu do transformers 5.x)
        lr_scheduler_type=tc.get("lr_scheduler", "cosine"),
        bf16=True,
        logging_steps=10,
        eval_strategy="no" if pilot or not val_sets else "steps",
        eval_steps=tc["eval_steps"],
        save_strategy="no" if pilot else "steps",
        save_steps=tc["eval_steps"],
        save_total_limit=3,
        load_best_model_at_end=not pilot and bool(val_sets),
        metric_for_best_model=tc["best_metric"],
        greater_is_better=False,
        remove_unused_columns=False,
        dataloader_num_workers=tc["dataloader_workers"],
        report_to="none",
        seed=cfg["seed"],
    )
    trainer = make_trainer(
        curriculum, cfg["seed"], train_rows,
        model=model, args=targs,
        eval_dataset=None if pilot or not val_sets else val_sets, data_collator=collator,
        callbacks=[] if pilot or not val_sets else [EarlyStoppingCallback(tc["early_stopping_patience"])],
    )
    t0 = time.time()
    resume = args.resume and not pilot and any(paths["checkpoints"].glob("checkpoint-*"))
    if resume:
        print("  continuando do último checkpoint em", paths["checkpoints"])
    result = trainer.train(resume_from_checkpoint=True if resume else None)
    elapsed = time.time() - t0
    m = result.metrics
    sps = m.get("train_samples_per_second", 0) or 0
    resumo = {
        "piloto": pilot, "segundos": round(elapsed, 1), "metricas": m,
        "exemplos": {"total": len(train_rows), "paginas": n_pages}, "curriculo": curriculum,
        "amostras_por_segundo": sps,
        "estimativa_horas_por_epoca": round(len(train_rows) / sps / 3600, 2) if sps else None,
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "memoria_pico_gb": round(torch.cuda.max_memory_allocated() / 1e9, 1)
        if torch.cuda.is_available() else None,
    }
    if not pilot:
        resumo["melhor_checkpoint"] = trainer.state.best_model_checkpoint
        resumo["melhor_eval_loss"] = trainer.state.best_metric
        resumo["historico"] = trainer.state.log_history
        model.save_pretrained(paths["adapter"])
        processor.save_pretrained(paths["adapter"])
    out = paths["run"] / ("piloto.json" if pilot else "treino.json")
    out.write_text(json.dumps(resumo, indent=2, ensure_ascii=False, default=str))
    print(f"== {'piloto' if pilot else 'treino'}: {sps:.2f} amostras/s, "
          f"~{resumo['estimativa_horas_por_epoca']} h/época, pico {resumo['memoria_pico_gb']} GB")
    print(f"   resumo em {out}")


if __name__ == "__main__":
    main()
