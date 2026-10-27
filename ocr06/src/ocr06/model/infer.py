"""Inferência com vLLM sobre os conjuntos de teste (roda no ambiente .venv-vllm).

    python -m ocr06.model.infer --models base base_fp8 --prompts nosso chandra
    python -m ocr06.model.infer --models ft ft_fp8

Modelos: base (Chandra BF16), base_fp8 (Chandra FP8), ft (fine-tunado, BF16),
ft_fp8 (fine-tunado, FP8). Prompts: `nosso` (transcrição literal da linha, o mesmo do
treino) e `chandra` (prompt nativo, saída em HTML; o HTML é removido na avaliação).
Saída: experiments/modelos/<modelo>/<prompt>/<split>.jsonl com {id, source, text, pred,
entities, guard}. O prompt é montado com o chat template do próprio modelo (o mesmo usado
no treino). A imagem passa pela mesma normalização de altura do treino (preprocess.py),
o limite de tokens de cada linha sai da largura da imagem e a saída passa pelos
controles de guard.py (confiança por palavra a partir das log-probs e sinais de revisão).
"""
from __future__ import annotations

import argparse
import gc
import json
import time
from pathlib import Path

from ..evaluate import normalize
from ..guard import check, tokens_from_vllm
from ..preprocess import load_line, max_chars
from . import ROOT, data_dir, final_dir, load_config, model_ref, resolve

SPLITS = ("test_sintetico", "test_bressay")


def load_rows(path: Path, limit: int | None) -> list[dict]:
    rows = [json.loads(line) for line in open(path, encoding="utf-8")]
    return rows[:limit] if limit else rows


def prompt_text(cfg: dict, name: str, row: dict) -> str:
    if name == "nosso":
        return row["messages"][0]["content"][1]["text"]
    return (ROOT / cfg["model"]["chandra_prompt_file"]).read_text(encoding="utf-8").strip()


def run_model(cfg: dict, tag: str, prompts: list[str], splits: list[str], limit: int | None):
    from transformers import AutoProcessor
    from vllm import LLM, SamplingParams

    ref = model_ref(cfg, tag)
    vc = cfg["model"]["vllm"]
    print(f"== vLLM: carregando {tag} ({ref})")
    processor = AutoProcessor.from_pretrained(ref, trust_remote_code=True)
    llm = LLM(model=ref, trust_remote_code=True, max_model_len=vc["max_model_len"],
              gpu_memory_utilization=vc["gpu_memory_utilization"],
              max_num_seqs=vc["max_num_seqs"], limit_mm_per_prompt={"image": 1},
              mm_processor_kwargs={"min_pixels": vc["min_pixels"], "max_pixels": vc["max_pixels"]},
              seed=cfg["seed"])
    n_logprobs = cfg.get("guard", {}).get("logprobs", 1)
    ddir = data_dir(cfg)
    out_root = resolve(cfg, "experiments") / "modelos" / tag

    for pname in prompts:
        for split in splits:
            rows = load_rows(final_dir(cfg) / f"{split}.jsonl", limit)
            reqs, params, limits = [], [], []
            for r in rows:
                msgs = [{"role": "user", "content": [{"type": "image"},
                                                     {"type": "text", "text": prompt_text(cfg, pname, r)}]}]
                prompt = processor.apply_chat_template(msgs, tokenize=False,
                                                       add_generation_prompt=True,
                                                       enable_thinking=False)
                img = load_line(ddir / r["image"], cfg)
                reqs.append({"prompt": prompt, "multi_modal_data": {"image": img}})
                # Limite por linha: o que cabe na largura da imagem (o prompt nativo
                # responde em HTML, então ganha folga para as tags).
                limit = max_chars(img.width, img.height, cfg)
                limits.append(limit)
                max_tok = min(vc["max_tokens"], limit if pname == "nosso" else limit + 32)
                params.append(SamplingParams(temperature=0.0, max_tokens=max_tok,
                                             logprobs=n_logprobs))
            t0 = time.time()
            outs = llm.generate(reqs, params)
            dt = time.time() - t0
            out_dir = out_root / pname
            out_dir.mkdir(parents=True, exist_ok=True)
            with open(out_dir / f"{split}.jsonl", "w", encoding="utf-8") as f:
                for r, o, limit in zip(rows, outs, limits):
                    out = o.outputs[0]
                    g = check(out.text, normalize(out.text), limit, cfg, tokens_from_vllm(out),
                              allow_html=pname == "chandra")
                    f.write(json.dumps({"id": r["id"], "source": r["source"], "text": r["text"],
                                        "pred": out.text, "entities": r["entities"], "guard": g},
                                       ensure_ascii=False) + "\n")
            (out_dir / f"{split}.tempo.json").write_text(json.dumps(
                {"modelo": ref, "linhas": len(rows), "segundos": round(dt, 1),
                 "linhas_por_segundo": round(len(rows) / dt, 2)}, indent=2))
            print(f"  {tag}/{pname}/{split}: {len(rows)} linhas em {dt:.0f}s "
                  f"({len(rows) / dt:.1f} linhas/s)")

    del llm
    gc.collect()
    try:
        import torch
        torch.cuda.empty_cache()
    except Exception:
        pass


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--models", nargs="+", required=True, help="base base_fp8 ft ft_fp8")
    ap.add_argument("--prompts", nargs="+", default=["nosso"], choices=["nosso", "chandra"])
    ap.add_argument("--splits", nargs="+", default=list(SPLITS), choices=SPLITS)
    ap.add_argument("--limit", type=int, help="só as N primeiras linhas (teste rápido)")
    args = ap.parse_args()
    cfg = load_config(args.config)
    for tag in args.models:
        run_model(cfg, tag, args.prompts, args.splits, args.limit)


if __name__ == "__main__":
    main()
