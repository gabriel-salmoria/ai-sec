"""Inferência em páginas inteiras com vLLM (ambiente .venv-vllm), para o teste de pages.py.

    python -m ocr06.model.pages_infer --models base ft --sets portexto bressay xfund_hw

Usa o prompt nativo do Chandra (layout), como numa página de verdade. Lê
data/pages/<conjunto>/pages.jsonl e grava experiments/paginas/<modelo>/<conjunto>.jsonl
({id, pred}). Pontuação: `python -m ocr06.pages score` (xfund_hw) e
`python -m ocr06.pages_real score` (portexto, bressay).
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import time

os.environ.setdefault("VLLM_USE_FLASHINFER_SAMPLER", "0")  # ver infer.py

from PIL import Image

from . import ROOT, data_dir, load_config, model_ref, resolve

NAME = "xfund_hw"


def _load(path, max_side: int) -> Image.Image:
    """Página com o lado maior <= max_side (o mesmo tamanho usado no treino de páginas)."""
    im = Image.open(path).convert("RGB")
    f = max_side / max(im.size)
    if f < 1:
        im = im.resize((round(im.width * f), round(im.height * f)), Image.LANCZOS)
    return im


def run(cfg: dict, tag: str, sets: list[str], limit: int | None, out_name: str | None = None) -> None:
    from transformers import AutoProcessor
    from vllm import LLM, SamplingParams

    vc, pc = cfg["model"]["vllm"], cfg["model"]["vllm_pages"]
    ref = model_ref(cfg, tag)
    prompt_text = (ROOT / cfg["model"]["chandra_prompt_file"]).read_text(encoding="utf-8").strip()
    print(f"== páginas: {tag} ({ref}), conjuntos {sets}")
    processor = AutoProcessor.from_pretrained(ref, trust_remote_code=True)
    llm = LLM(model=ref, trust_remote_code=True, max_model_len=pc["max_model_len"],
              gpu_memory_utilization=vc["gpu_memory_utilization"],
              max_num_seqs=pc["max_num_seqs"], limit_mm_per_prompt={"image": 1},
              mm_processor_kwargs={"min_pixels": vc["min_pixels"], "max_pixels": vc["max_pixels"]},
              seed=cfg["seed"])
    msgs = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt_text}]}]
    prompt = processor.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True,
                                           enable_thinking=False)
    stop_ids = [i for i in (processor.tokenizer.convert_tokens_to_ids(t)
                            for t in ("<|im_end|>", "<|endoftext|>")) if isinstance(i, int)]
    params = SamplingParams(temperature=0.0, max_tokens=pc["max_tokens"], stop_token_ids=stop_ids)
    out_dir = resolve(cfg, "experiments") / "paginas" / (out_name or tag)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in sets:
        path = data_dir(cfg) / "pages" / name / "pages.jsonl"
        rows = [json.loads(line) for line in open(path, encoding="utf-8")][:limit]
        reqs = [{"prompt": prompt, "multi_modal_data": {
                    "image": _load(data_dir(cfg) / r["image"], pc.get("max_side", 2048))}} for r in rows]
        t0 = time.time()
        outs = llm.generate(reqs, params)
        dt = time.time() - t0
        with open(out_dir / f"{name}.jsonl", "w", encoding="utf-8") as f:
            for r, o in zip(rows, outs):
                out = o.outputs[0]
                f.write(json.dumps({"id": r["id"], "pred": out.text,
                                    "tokens": len(out.token_ids), "fim": out.finish_reason},
                                   ensure_ascii=False) + "\n")
        (out_dir / f"{name}.tempo.json").write_text(json.dumps(
            {"modelo": ref, "paginas": len(rows), "segundos": round(dt, 1)}, indent=2))
        print(f"  {tag}/{name}: {len(rows)} páginas em {dt:.0f}s")
    del llm
    gc.collect()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--models", nargs="+", default=["base", "ft"])
    ap.add_argument("--sets", nargs="+", default=[NAME])
    ap.add_argument("--limit", type=int)
    ap.add_argument("--out-name", help="pasta de saída (ex.: lora_v0), em vez do nome curto do modelo")
    args = ap.parse_args()
    cfg = load_config(args.config)
    for tag in args.models:
        run(cfg, tag, args.sets, args.limit, args.out_name if len(args.models) == 1 else None)


if __name__ == "__main__":
    main()
