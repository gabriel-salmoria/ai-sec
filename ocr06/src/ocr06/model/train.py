"""Fine-tuning LoRA do Chandra (BF16) com transformers + peft (ambiente .venv-gpu).

    python -m ocr06.model.train            # treino completo (config: model.train)
    python -m ocr06.model.train --pilot    # poucos passos, só para medir velocidade

Lê data/final/<dataset>/{train,val}.jsonl. O encoder de visão fica congelado; o LoRA
entra só nas camadas lineares do modelo de linguagem. A perda é calculada apenas na
resposta (a transcrição), não no prompt nem na imagem. A validação usa a perda em
`max_val` linhas a cada `eval_steps`, com parada antecipada e o melhor checkpoint salvo.
Saída: models/<run>/adapter/ (adaptador + processor) e models/<run>/treino.json.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import time

import torch
from PIL import Image

from . import data_dir, final_dir, load_config, model_paths


def load_jsonl(path) -> list[dict]:
    return [json.loads(line) for line in open(path, encoding="utf-8")]


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


class Collator:
    """Monta o lote e mascara (-100) tudo que não é a resposta do assistente."""

    def __init__(self, processor, ddir):
        self.p = processor
        self.ddir = ddir
        self.p.tokenizer.padding_side = "right"

    def _template(self, messages, generation_prompt: bool) -> str:
        return self.p.apply_chat_template(messages, tokenize=False,
                                          add_generation_prompt=generation_prompt,
                                          enable_thinking=False)

    def __call__(self, rows: list[dict]) -> dict:
        images = [Image.open(self.ddir / r["image"]).convert("RGB") for r in rows]
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


def main() -> None:
    from peft import LoraConfig, get_peft_model
    from transformers import (AutoModelForImageTextToText, AutoProcessor, EarlyStoppingCallback,
                              Trainer, TrainingArguments)

    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--pilot", action="store_true", help="poucos passos para medir velocidade")
    args = ap.parse_args()
    cfg = load_config(args.config)
    mc, tc, lc = cfg["model"], cfg["model"]["train"], cfg["model"]["lora"]
    paths = model_paths(cfg)
    paths["run"].mkdir(parents=True, exist_ok=True)
    rng = random.Random(cfg["seed"])

    train_rows = load_jsonl(final_dir(cfg) / "train.jsonl")
    val_rows = load_jsonl(final_dir(cfg) / "val.jsonl")
    if len(val_rows) > tc["max_val"]:
        val_rows = rng.sample(val_rows, tc["max_val"])
    print(f"== treino: {len(train_rows)} linhas | validação: {len(val_rows)} linhas")

    processor = AutoProcessor.from_pretrained(mc["base"], trust_remote_code=True)
    model = AutoModelForImageTextToText.from_pretrained(
        mc["base"], dtype=torch.bfloat16, trust_remote_code=True, attn_implementation="sdpa")
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.enable_input_require_grads()
    model = get_peft_model(model, LoraConfig(
        r=lc["r"], lora_alpha=lc["alpha"], lora_dropout=lc["dropout"],
        target_modules=lora_target_regex(model, lc["target"]), bias="none"))
    model.print_trainable_parameters()

    collator = Collator(processor, data_dir(cfg))
    # Mostra o que o modelo vai aprender no 1º exemplo (confere a máscara do prompt).
    b = collator(train_rows[:1])
    alvo = processor.tokenizer.decode(b["labels"][0][b["labels"][0] != -100])
    print(f"  alvo do 1º exemplo: {alvo!r}  (esperado: {train_rows[0]['text']!r} + fim de turno)")

    pilot = args.pilot
    targs = TrainingArguments(
        output_dir=str(paths["checkpoints"]),
        per_device_train_batch_size=tc["batch_size"],
        per_device_eval_batch_size=tc["batch_size"],
        gradient_accumulation_steps=tc["grad_accum"],
        learning_rate=tc["lr"],
        num_train_epochs=tc["epochs"],
        max_steps=tc["pilot_steps"] if pilot else -1,
        warmup_ratio=tc["warmup_ratio"],
        lr_scheduler_type="cosine",
        bf16=True,
        logging_steps=10,
        eval_strategy="no" if pilot else "steps",
        eval_steps=tc["eval_steps"],
        save_strategy="no" if pilot else "steps",
        save_steps=tc["eval_steps"],
        save_total_limit=3,
        load_best_model_at_end=not pilot,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        remove_unused_columns=False,
        dataloader_num_workers=tc["dataloader_workers"],
        report_to="none",
        seed=cfg["seed"],
    )
    trainer = Trainer(
        model=model, args=targs, train_dataset=train_rows,
        eval_dataset=None if pilot else val_rows, data_collator=collator,
        callbacks=[] if pilot else [EarlyStoppingCallback(tc["early_stopping_patience"])],
    )
    t0 = time.time()
    result = trainer.train()
    elapsed = time.time() - t0
    m = result.metrics
    sps = m.get("train_samples_per_second", 0) or 0
    resumo = {
        "piloto": pilot, "segundos": round(elapsed, 1), "metricas": m,
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
