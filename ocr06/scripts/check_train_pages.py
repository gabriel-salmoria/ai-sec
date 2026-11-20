"""Conferência em CPU do treino de páginas (src/ocr06/model/train.py), sem os pesos do Chandra.

Usa o tokenizer, o processor e o config reais do datalab-to/chandra-ocr-2 (só os .json,
~20 MB; os 10 GB de pesos não são baixados) e um modelo aleatório minúsculo com a mesma
arquitetura (Qwen3.5: atenção linear + completa, visão com fusão 2x2, mesmo vocabulário).

    uv venv --python 3.12 .venv-cputest
    uv pip install --python .venv-cputest/bin/python --index-url https://download.pytorch.org/whl/cpu \\
        --extra-index-url https://pypi.org/simple --index-strategy unsafe-best-match \\
        torch==2.10.0 torchvision==0.25.0 transformers==5.21.0 accelerate==1.15.0 peft==0.21.2 \\
        numpy pillow pyyaml requests tqdm pytest opencv-python-headless
    .venv-cputest/bin/python scripts/check_train_pages.py            # pesos, perda, currículo
    .venv-cputest/bin/python scripts/check_train_pages.py --tokens   # tokens por página e custo

O que confere (e para com erro se falhar):
  1. pesos: os tokens de peso 1 de cada página são exatamente os trechos manuscritos
     (decodificados e comparados com o texto de cada trecho); máscara w=0 zera o trecho;
     o resto da resposta tem `w_default`; prompt e imagem ficam fora;
  2. o nº de tokens do prompt obtido pela resposta tokenizada sozinha é o mesmo do método
     antigo (prompt + imagem processados de novo);
  3. lote só de linhas: input_ids, labels e pixels idênticos ao Collator antigo, sem pesos;
  4. perda ponderada com todos os pesos 1 e logits_to_keep = perda padrão do modelo;
  5. alguns passos de treino (LoRA, gradient checkpointing, lotes mistos página + linha)
     com perda finita, e a ordem do currículo vista pelo collator;
  6. train.main() de ponta a ponta com o modelo minúsculo no lugar do Chandra: validação
     com páginas (perda ponderada também na avaliação), melhor checkpoint e adaptador salvo.
"""
from __future__ import annotations

import argparse
import html
import json
import math
import os
import random
import statistics
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("HF_HOME", str(ROOT / "models" / "hf_cache"))

import torch  # noqa: E402

from ocr06.common import load_config  # noqa: E402
from ocr06.model import train as T  # noqa: E402
from ocr06.preprocess import load_line, load_page  # noqa: E402

BASE = "datalab-to/chandra-ocr-2"
DATA = ROOT / "data"


def processor_and_config(cfg):
    from huggingface_hub import snapshot_download
    from transformers import AutoConfig, AutoProcessor
    snap = snapshot_download(BASE, allow_patterns=["*.json", "*.jinja"])
    proc = AutoProcessor.from_pretrained(snap)
    proc.image_processor.size = {"shortest_edge": cfg["model"]["vllm"]["min_pixels"],
                                 "longest_edge": cfg["model"]["vllm"]["max_pixels"]}
    return proc, AutoConfig.from_pretrained(snap)


def tiny_model(config):
    """Mesma arquitetura do Chandra com tudo encolhido, exceto vocabulário e geometria da
    visão (patch 16, fusão 2x2, temporal 2), que o processor real exige."""
    # import do módulo (não de `transformers`), que check_main troca por um substituto
    from transformers.models.auto.modeling_auto import AutoModelForImageTextToText
    tc, vc = config.text_config, config.vision_config
    tc.hidden_size, tc.intermediate_size = 64, 128
    tc.num_hidden_layers, tc.layer_types = 4, tc.layer_types[:4]   # 3 lineares + 1 completa
    tc.num_attention_heads, tc.num_key_value_heads, tc.head_dim = 2, 1, 64
    tc.linear_num_key_heads, tc.linear_num_value_heads = 2, 4
    tc.linear_key_head_dim = tc.linear_value_head_dim = 16
    tc.rope_parameters["mrope_section"] = [3, 3, 2]                # 64 * 0,25 / 2 = 8
    vc.depth, vc.hidden_size, vc.intermediate_size, vc.num_heads = 2, 64, 128, 2
    vc.out_hidden_size = tc.hidden_size
    torch.manual_seed(0)
    return AutoModelForImageTextToText.from_config(config, dtype=torch.float32)


class OldCollator:
    """Collator do commit c427ff5 (treino das linhas, lora_v0), copiado sem mudança."""

    def __init__(self, processor, ddir, cfg):
        self.p, self.ddir, self.cfg = processor, ddir, cfg
        self.p.tokenizer.padding_side = "right"

    def _template(self, messages, generation_prompt):
        return self.p.apply_chat_template(messages, tokenize=False,
                                          add_generation_prompt=generation_prompt, enable_thinking=False)

    def __call__(self, rows):
        images = [load_line(self.ddir / r["image"], self.cfg) for r in rows]
        full = [self._template(r["messages"], False) for r in rows]
        batch = self.p(text=full, images=images, padding=True, return_tensors="pt")
        labels = batch["input_ids"].clone()
        for i, (r, img) in enumerate(zip(rows, images)):
            prompt = self._template(r["messages"][:1], True)
            n_prompt = self.p(text=[prompt], images=[img], return_tensors="pt")["input_ids"].shape[1]
            labels[i, :n_prompt] = -100
        labels[batch["attention_mask"] == 0] = -100
        batch["labels"] = labels
        return batch


# ----------------------------------------------------------------------- exemplos

def matched_pages(n: int) -> list[tuple[dict, dict]]:
    """Páginas do OCRSD com gabarito e predição do Chandra base."""
    gold = {r["id"]: r for r in map(json.loads, open(DATA / "pages/ocrsd/pages.jsonl", encoding="utf-8"))}
    base = [json.loads(l) for l in open(ROOT / "experiments/paginas/base/ocrsd.jsonl", encoding="utf-8")]
    return [(gold[p["id"]], p) for p in base if p["id"] in gold][:n]


def page_row(gold: dict, pred: dict, level: int, prompt: str, max_chars: int, mask_one: bool) -> dict:
    """Exemplo de página: alvo = saída do Chandra base na página (formato nativo, cortada
    num fim de bloco), trechos = onde os valores manuscritos do gabarito aparecem nela."""
    target = pred["pred"]
    if len(target) > max_chars:
        target = target[:target.rfind("</div>", 0, max_chars) + len("</div>")]
    spans, used = [], set()
    for f in gold["fields"]:
        t = html.escape(f["text"], quote=False)
        if len(t) <= 3:
            continue
        s = target.find(t)
        while s in used:
            s = target.find(t, s + 1)
        if s < 0 or any(s < b["end"] and s + len(t) > b["start"] for b in spans):
            continue
        used.add(s)
        spans.append({"start": s, "end": s + len(t), "w": 0.0 if f.get("accent_stripped") else 1.0,
                      "text": t})
    spans.sort(key=lambda b: b["start"])
    if mask_one and spans:
        spans[0]["w"] = 0.0  # simula um campo com acento perdido: deve sair da perda
    return {"id": gold["id"], "source": "ocrsd", "image": gold["image"], "template": gold["template"],
            "level": level,
            "messages": [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt}]},
                         {"role": "assistant", "content": [{"type": "text", "text": target}]}],
            "spans": spans, "w_default": 0.3}


def real_rows(path: Path, n: int, max_chars: int) -> list[dict]:
    """Exemplos reais de forms/targets.py (um por nível), com o alvo cortado num fim de bloco
    e só os trechos que cabem no corte (memória da CPU)."""
    rows, levels = [], set()
    for r in map(json.loads, open(path, encoding="utf-8")):
        if r.get("level") in levels or len(rows) >= n:
            continue
        levels.add(r.get("level"))
        msg = r["messages"][-1]["content"][0]
        t = msg["text"]
        if len(t) > max_chars:
            msg["text"] = t = t[:t.rfind("</div>", 0, max_chars) + len("</div>")]
        r["spans"] = [{**sp, "text": t[sp["start"]:sp["end"]]} for sp in r["spans"] if sp["end"] <= len(t)]
        rows.append(r)
    return rows


def line_rows(work: Path, prompt_chandra: str, n: int = 2) -> list[dict]:
    """Linhas no formato de mix.py, recortadas dos campos de nome de uma página OCRSD."""
    from PIL import Image
    from ocr06.mix import PROMPT, ink_bbox
    gold, _ = matched_pages(1)[0]
    page = Image.open(DATA / gold["image"]).convert("RGB")
    (work / "lines").mkdir(parents=True, exist_ok=True)
    rows = []
    for k, f in enumerate([f for f in gold["fields"] if f["cls"] == "name"][:n]):
        x0, y0, x1, y1 = f["box"]
        rel = f"lines/l{k}.jpg"
        page.crop((x0 - 8, y0 - 8, x1 + 8, y1 + 8)).save(work / rel, quality=92)
        if k % 2 == 0:
            msgs = [{"type": "text", "text": PROMPT}], f["text"]
        else:
            box = ink_bbox(str(work / rel))
            msgs = ([{"type": "text", "text": prompt_chandra}],
                    f'<div data-bbox="{box}" data-label="Text"><p>{html.escape(f["text"], quote=False)}</p></div>')
        rows.append({"id": f"linha_{k}", "source": "sintetico", "image": rel, "text": f["text"],
                     "messages": [{"role": "user", "content": [{"type": "image"}] + msgs[0]},
                                  {"role": "assistant", "content": [{"type": "text", "text": msgs[1]}]}]})
    return rows


def data_root(work: Path) -> Path:
    """Pasta com lines/ (recortes) e pages/ -> data/pages, para o Collator achar as duas."""
    if not (work / "pages").exists():
        (work / "pages").symlink_to(DATA / "pages")
    return work


# ----------------------------------------------------------------------- conferências

def runs(mask) -> list[tuple[int, int]]:
    out, start = [], None
    for i, v in enumerate(mask + [False]):
        if v and start is None:
            start = i
        elif not v and start is not None:
            out.append((start, i))
            start = None
    return out


def check_weights(proc, collator, rows) -> None:
    tok = proc.tokenizer
    for r in rows:
        b = collator([r])
        ids, lab, w = b["input_ids"][0], b["labels"][0], b["loss_weights"][0]
        tgt = lab != -100
        # (2) n_prompt pela resposta sozinha == método antigo (prompt + imagem de novo)
        prompt = collator._template(r["messages"][:1], True)
        img = collator.image(r)
        n_old = proc(text=[prompt], images=[img], return_tensors="pt")["input_ids"].shape[1]
        n_new = int(tgt.nonzero()[0])
        assert n_old == n_new, (r["id"], n_old, n_new)
        assert (w[~tgt] == 0).all(), "peso fora do alvo"
        n_img = int((ids == proc.tokenizer.convert_tokens_to_ids("<|image_pad|>")).sum())
        print(f"\n== {r['id']} (nível {r['level']}): {int(b['attention_mask'][0].sum())} tokens = "
              f"{n_img} de imagem + {n_new - n_img} de prompt + {int(tgt.sum())} de resposta; "
              f"imagem {tuple(img.size)}")
        hist = {}
        for x in w[tgt].tolist():
            hist[round(x, 2)] = hist.get(round(x, 2), 0) + 1
        print(f"   pesos na resposta: {dict(sorted(hist.items()))}")
        # (1) cada trecho de peso 1 vira uma sequência de tokens de peso 1 que o contém
        hi = runs((w >= 1.0).tolist())
        pieces = [tok.decode(ids[a:c]) for a, c in hi]
        end = tok.decode(ids[hi[-1][0]:hi[-1][1]])
        assert end.endswith("<|im_end|>\n"), end
        pieces = pieces[:-1] if pieces[-1] == "<|im_end|>\n" else pieces[:-1] + [end[:-len("<|im_end|>\n")]]
        want = [s["text"] for s in r["spans"] if s["w"] >= 1.0]
        assert len(pieces) == len(want), (len(pieces), len(want))
        for p, s in zip(pieces, want):
            assert html.unescape(s) in html.unescape(p) or s in p, (p, s)
            assert len(p) - len(s) <= 6, f"peso 1 vazou além do trecho: {p!r} x {s!r}"
        zero = [s["text"] for s in r["spans"] if s["w"] == 0.0]
        zero_runs = [tok.decode(ids[a:c]) for a, c in runs(((w == 0) & tgt).tolist())]
        for s in zero:
            assert any(s in z for z in zero_runs), f"trecho mascarado ainda na perda: {s!r}"
        print(f"   {len(want)} trechos de peso 1, decodificados (tokens de peso 1 | texto do trecho):")
        for p, s in list(zip(pieces, want))[:8]:
            print(f"     {p!r:48} | {s!r}")
        if len(want) > 8:
            print(f"     ... (+{len(want) - 8}, todos conferidos)")
        for s in zero:
            print(f"   trecho com w=0 fora da perda: {s!r}")
        print("   fim de turno com peso 1: '<|im_end|>\\n'")


def check_lines_unchanged(proc, collator, old, lines) -> None:
    b, o = collator(lines), old(lines)
    assert "loss_weights" not in b
    for k in ("input_ids", "attention_mask", "labels", "pixel_values", "image_grid_thw"):
        assert torch.equal(b[k], o[k]), k
    alvo = [proc.tokenizer.decode(l[l != -100]) for l in b["labels"]]
    print(f"\n== lote só de linhas: idêntico ao Collator antigo (input_ids, labels, pixels); alvos {alvo}")


def check_loss_equivalence(model, collator, rows) -> None:
    from copy import deepcopy
    ones = []
    for r in rows:
        r = deepcopy(r)
        r["w_default"] = 1.0
        for s in r["spans"]:
            s["w"] = 1.0
        ones.append(r)
    b = collator(ones)
    model.eval()
    with torch.no_grad():
        inputs = {k: v for k, v in b.items() if k not in ("labels", "loss_weights")}
        ref = model(**inputs, labels=b["labels"]).loss
        lab = b["labels"]
        first = int((lab != -100).any(0).nonzero()[0])
        keep = lab.shape[1] - first + 1
        out = model(**inputs, logits_to_keep=keep)
        mine = T.weighted_lm_loss(out.logits, lab, b["loss_weights"])
    model.train()
    print(f"\n== perda ponderada (pesos 1, logits só nas últimas {keep} de {lab.shape[1]} posições) = "
          f"{mine.item():.6f}; perda padrão do modelo = {ref.item():.6f}")
    assert torch.allclose(mine, ref, rtol=1e-4, atol=1e-5)


def check_training(model, proc, collator, rows, cfg, steps: int, work: Path) -> None:
    from peft import LoraConfig, get_peft_model
    from transformers import TrainingArguments
    lc = cfg["model"]["lora"]
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.enable_input_require_grads()
    model = get_peft_model(model, LoraConfig(r=lc["r"], lora_alpha=lc["alpha"], lora_dropout=lc["dropout"],
                                             target_modules=T.lora_target_regex(model, lc["target"]),
                                             bias="none"))
    seen = []

    def logging_collator(batch_rows):
        seen.append([(r["id"], r.get("level")) for r in batch_rows])
        return collator(batch_rows)

    args = TrainingArguments(output_dir=str(work / "ckpt"), per_device_train_batch_size=2,
                             gradient_accumulation_steps=1, learning_rate=1e-3, max_steps=steps,
                             warmup_steps=0, lr_scheduler_type="cosine", logging_steps=1, use_cpu=True,
                             bf16=False, eval_strategy="no", save_strategy="no", report_to="none",
                             remove_unused_columns=False, dataloader_num_workers=0, seed=cfg["seed"])
    trainer = T.make_trainer(True, cfg["seed"], rows, model=model, args=args, data_collator=logging_collator)
    trainer.train()
    losses = [h["loss"] for h in trainer.state.log_history if "loss" in h]
    print(f"\n== treino: {steps} passos, lote 2 (LoRA, gradient checkpointing, currículo ligado)")
    for k, (batch, loss) in enumerate(zip(seen, losses)):
        print(f"   passo {k + 1}: perda {loss:.4f}  lote {[(i[:34], lv) for i, lv in batch]}")
    assert losses and all(math.isfinite(x) for x in losses), losses
    levels = [lv for batch in seen for _, lv in batch if lv is not None]
    assert levels == sorted(levels), levels
    expected = [rows[i]["id"] for i in T.curriculum_order(rows, cfg["seed"])]
    assert [i for batch in seen for i, _ in batch] == expected[:len(seen) * 2]
    print("   ordem conferida: níveis crescentes, linhas (nível None) intercaladas")


def check_main(cfg, proc, config, rows, val_rows, work: Path) -> None:
    """train.main() de ponta a ponta (validação com páginas, parada antecipada, melhor
    checkpoint, adaptador salvo), com o modelo minúsculo no lugar do Chandra e tudo em `work`."""
    from copy import deepcopy
    import transformers
    c = deepcopy(cfg)
    c["model"]["train"].update(batch_size=2, grad_accum=1, epochs=1, eval_steps=2, lr=1e-3, warmup_ratio=0,
                               max_val={"ocrsd": 2, "sintetico": 1, "bressay": 5},
                               best_metric="eval_ocrsd_loss", dataloader_workers=0, curriculum=True)
    final, run = work / "final", work / "run"
    final.mkdir(parents=True, exist_ok=True)
    for name, rs in (("train", rows), ("val", val_rows)):
        with open(final / f"{name}.jsonl", "w", encoding="utf-8") as f:
            for r in rs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    class StubModel:
        @staticmethod
        def from_pretrained(*_, **__):
            return tiny_model(deepcopy(config))

    class StubProcessor:
        @staticmethod
        def from_pretrained(*_, **__):
            return proc

    real_args = transformers.TrainingArguments

    def cpu_args(**kw):  # bf16 de train.py exige GPU; na CPU roda em fp32
        return real_args(**{**kw, "bf16": False, "use_cpu": True})

    saved = (T.load_config, T.final_dir, T.data_dir, T.model_paths, transformers.AutoModelForImageTextToText,
             transformers.AutoProcessor, transformers.TrainingArguments, sys.argv)
    T.load_config, T.final_dir, T.data_dir = (lambda *_: c), (lambda _: final), (lambda _: work)
    T.model_paths = lambda _: {"run": run, "adapter": run / "adapter", "checkpoints": run / "checkpoints"}
    transformers.AutoModelForImageTextToText, transformers.AutoProcessor = StubModel, StubProcessor
    transformers.TrainingArguments = cpu_args
    sys.argv = ["train"]
    print("\n== train.main() de ponta a ponta (modelo minúsculo, validação ocrsd + sintetico)")
    try:
        T.main()
    finally:
        (T.load_config, T.final_dir, T.data_dir, T.model_paths, transformers.AutoModelForImageTextToText,
         transformers.AutoProcessor, transformers.TrainingArguments, sys.argv) = saved
    res = json.loads((run / "treino.json").read_text())
    evals = [(h["step"], {k: round(v, 4) for k, v in h.items() if k.endswith("_loss")})
             for h in res["historico"] if any(k.startswith("eval_") and k.endswith("_loss") for k in h)]
    print(f"   validação: {evals}")
    print(f"   melhor checkpoint {Path(res['melhor_checkpoint']).name}, eval_ocrsd_loss {res['melhor_eval_loss']:.4f}; "
          f"adaptador salvo: {(run / 'adapter' / 'adapter_model.safetensors').exists()}")
    assert evals and all(math.isfinite(v) for _, d in evals for v in d.values())
    assert (run / "adapter" / "adapter_model.safetensors").exists()


# ----------------------------------------------------------------------- tokens e custo

def pctl(v, q):
    v = sorted(v)
    return v[min(len(v) - 1, max(0, round(q * (len(v) - 1))))]


def dist(v) -> str:
    return (f"min {min(v)}, p10 {pctl(v, .1)}, mediana {pctl(v, .5)}, média {statistics.mean(v):.0f}, "
            f"p90 {pctl(v, .9)}, máx {max(v)}")


def token_estimate(cfg, proc, work: Path, n_pages: int, max_side: int) -> dict:
    from PIL import Image
    from ocr06.mix import PROMPT, ink_bbox
    tok = proc.tokenizer
    prompt_chandra = (ROOT / cfg["model"]["chandra_prompt_file"]).read_text(encoding="utf-8").strip()
    msgs = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt_chandra}]}]
    gen_prompt = proc.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, enable_thinking=False)
    n_end = len(tok("<|im_end|>\n", add_special_tokens=False)["input_ids"])

    def page_stats(name, pairs):
        img_t, txt_t, out_t, tot = [], [], [], []
        for row, pred in pairs:
            im = load_page(DATA / row["image"], max_side)
            n_all = proc(text=[gen_prompt], images=[im], return_tensors="pt")["input_ids"].shape[1]
            g = proc.image_processor(images=[im], return_tensors="pt")["image_grid_thw"][0]
            n_img = int(g.prod()) // proc.image_processor.merge_size ** 2
            n_out = len(tok(pred["pred"], add_special_tokens=False)["input_ids"]) + n_end
            img_t.append(n_img), txt_t.append(n_all - n_img), out_t.append(n_out), tot.append(n_all + n_out)
        print(f"\n== {name}: {len(pairs)} páginas, lado maior {max_side} px")
        print(f"   tokens de imagem: {dist(img_t)}")
        print(f"   prompt nativo + template: {dist(txt_t)}")
        print(f"   resposta (saída do Chandra base + fim de turno): {dist(out_t)}")
        print(f"   total por exemplo: {dist(tot)}")
        return {"imagem": img_t, "prompt": txt_t, "resposta": out_t, "total": tot}

    res = {"ocrsd": page_stats("OCRSD", matched_pages(n_pages))}
    bre_gold = {r["id"]: r for r in map(json.loads, open(DATA / "pages/bressay/pages.jsonl", encoding="utf-8"))}
    bre = [(bre_gold[p["id"]], p) for p in map(json.loads, open(ROOT / "experiments/paginas/base/bressay.jsonl",
                                                                 encoding="utf-8"))
           if p["id"] in bre_gold and p.get("fim") == "stop"]
    res["bressay"] = page_stats("BRESSAY (teste; fim=stop, sem os laços)", bre)

    # Linhas: recortes de campos de nome/lugar das páginas OCRSD, com altura normalizada,
    # nos dois formatos de mix.py ("misto": metade com cada prompt).
    (work / "lines").mkdir(parents=True, exist_ok=True)
    per_fmt = {"nosso": [], "chandra": []}
    k = 0
    for row, _ in matched_pages(n_pages):
        page = Image.open(DATA / row["image"]).convert("RGB")
        for f in row["fields"]:
            if f["cls"] not in ("name", "place") or len(f["text"]) > 60 or k >= 48:
                continue
            x0, y0, x1, y1 = f["box"]
            path = work / "lines" / f"tok_{k}.jpg"
            page.crop((x0 - 8, y0 - 8, x1 + 8, y1 + 8)).save(path, quality=92)
            img = load_line(path, cfg)
            for fmt in per_fmt:
                if fmt == "nosso":
                    m = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": PROMPT}]},
                         {"role": "assistant", "content": [{"type": "text", "text": f["text"]}]}]
                else:
                    ans = f'<div data-bbox="{ink_bbox(str(path))}" data-label="Text"><p>{f["text"]}</p></div>'
                    m = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt_chandra}]},
                         {"role": "assistant", "content": [{"type": "text", "text": ans}]}]
                full = proc.apply_chat_template(m, tokenize=False, enable_thinking=False)
                per_fmt[fmt].append(proc(text=[full], images=[img], return_tensors="pt")["input_ids"].shape[1])
            k += 1
    rng = random.Random(0)
    mixed = per_fmt["nosso"] + per_fmt["chandra"]
    padded = [max(rng.choice(per_fmt[rng.choice(list(per_fmt))]) for _ in range(16)) for _ in range(2000)]
    print(f"\n== linhas ({k} recortes de nome/lugar, altura {cfg['preprocess']['line_height']} px)")
    for fmt, v in per_fmt.items():
        print(f"   prompt {fmt}: {dist(v)}")
    print(f"   misto (50/50): média {statistics.mean(mixed):.0f} tokens; lote de 16 com preenchimento "
          f"até o maior: {statistics.mean(padded):.0f} tokens por exemplo")
    res["linhas"] = {"nosso": per_fmt["nosso"], "chandra": per_fmt["chandra"],
                     "media": statistics.mean(mixed), "media_preenchida_lote16": statistics.mean(padded)}

    # Escala a partir do treino das linhas (models/lora_v0/treino.json)
    tj = json.loads((ROOT / "models/lora_v0/treino.json").read_text())
    sps = tj["amostras_por_segundo"]
    tok_s = {"sem preenchimento": sps * res["linhas"]["media"],
             "com preenchimento": sps * res["linhas"]["media_preenchida_lote16"]}
    print(f"\n== custo (linhas: {sps} exemplos/s na {tj['gpu']}, {tj['segundos'] / 3600:.2f} h)")
    out = {}
    for name, t in tok_s.items():
        print(f"   tokens/s do treino das linhas ({name}): {t:.0f}")
    for label, n, key in (("2.000 páginas OCRSD/locais", 2000, "ocrsd"), ("300 páginas BRESSAY", 300, "bressay")):
        mean_tok = statistics.mean(res[key]["total"])
        for name, t in tok_s.items():
            for fac in (1.0, 1.5):
                h = n * mean_tok / t * fac / 3600
                out[(label, name, fac)] = h
                print(f"   {label}: {mean_tok:.0f} tokens/ex., {name}, fator {fac}: "
                      f"{n * mean_tok / t * fac / n:.2f} s/ex., {h:.2f} h, {10 * h:.1f} CU")
    res["custo"] = {f"{a} | {b} | x{c}": v for (a, b, c), v in out.items()}
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--tokens", action="store_true", help="só a contagem de tokens e a estimativa de custo")
    ap.add_argument("--pages", type=int, default=4)
    ap.add_argument("--max-target-chars", type=int, default=2500,
                    help="corta o alvo das páginas (memória da CPU: logits de 248 mil por token)")
    ap.add_argument("--steps", type=int, default=3)
    ap.add_argument("--work", help="pasta temporária (padrão: uma nova em /tmp)")
    ap.add_argument("--rows", help="exemplos de página reais (ex.: data/final/pages_try/train.jsonl)")
    ap.add_argument("--skip-main", action="store_true", help="pula o train.main() de ponta a ponta")
    a = ap.parse_args()
    cfg = load_config(a.config)
    work = Path(a.work or tempfile.mkdtemp(prefix="check_train_pages_"))
    work.mkdir(parents=True, exist_ok=True)
    proc, config = processor_and_config(cfg)
    if a.tokens:
        res = token_estimate(cfg, proc, work, 50, cfg["model"]["train"].get("page_max_side", 2048))
        (work / "tokens.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
        print(f"\n-> {work / 'tokens.json'}")
        return
    prompt = (ROOT / cfg["model"]["chandra_prompt_file"]).read_text(encoding="utf-8").strip()
    if a.rows:
        pages = real_rows(ROOT / a.rows, a.pages, a.max_target_chars)
    else:
        pages = [page_row(g, p, lv, prompt, a.max_target_chars, mask_one=(k == 0))
                 for k, ((g, p), lv) in enumerate(zip(matched_pages(a.pages), [3, 1, 4, 2, 2, 3, 1, 4]))]
    lines = line_rows(work, prompt)
    ddir = data_root(work)
    collator = T.Collator(proc, ddir, cfg)
    check_weights(proc, collator, pages)
    check_lines_unchanged(proc, collator, OldCollator(proc, ddir, cfg), lines)
    model = tiny_model(config)
    print(f"\n== modelo minúsculo: {sum(p.numel() for p in model.parameters()) / 1e6:.1f} M parâmetros "
          f"(classe {type(model).__name__}, accepts_loss_kwargs={getattr(model, 'accepts_loss_kwargs', None)})")
    check_loss_equivalence(model, collator, pages[:2])
    rows = pages + lines
    order = [(rows[i]["id"][:34], rows[i].get("level")) for i in T.curriculum_order(rows, cfg["seed"])]
    print(f"\n== ordem do currículo (seed {cfg['seed']}): {order}")
    check_training(model, proc, collator, rows, cfg, a.steps, work)
    if not a.skip_main:
        val = [page_row(g, p, 2, prompt, a.max_target_chars, False) for g, p in matched_pages(a.pages + 2)[-2:]]
        check_main(cfg, proc, config, rows, val + lines[:1], work)
    print("\nOK: todas as conferências passaram.")


if __name__ == "__main__":
    main()
