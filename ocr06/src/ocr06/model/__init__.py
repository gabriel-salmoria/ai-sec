"""Etapas que usam o modelo (rodam só no servidor com GPU).

infer.py  -> vLLM (ambiente .venv-vllm)
train.py  -> LoRA com transformers + peft (ambiente .venv-gpu)
merge.py  -> funde o LoRA e quantiza em FP8 com llm-compressor (ambiente .venv-gpu)
"""
from __future__ import annotations

from pathlib import Path

from ..common import ROOT, load_config, resolve


def model_paths(cfg: dict) -> dict[str, Path]:
    run = ROOT / "models" / cfg["model"]["run"]
    return {"run": run, "adapter": run / "adapter", "merged": run / "merged",
            "merged_fp8": run / "merged-fp8", "checkpoints": run / "checkpoints"}


def final_dir(cfg: dict) -> Path:
    return resolve(cfg, "final") / cfg["model"]["dataset"]


def data_dir(cfg: dict) -> Path:
    return resolve(cfg, "raw").parent


def model_ref(cfg: dict, tag: str) -> str:
    """Tag curta -> caminho/ID do modelo: base, base_fp8, ft, ft_fp8."""
    p = model_paths(cfg)
    refs = {"base": cfg["model"]["base"], "base_fp8": cfg["model"]["base_fp8"],
            "ft": str(p["merged"]), "ft_fp8": str(p["merged_fp8"])}
    if tag not in refs:
        raise SystemExit(f"modelo desconhecido: {tag} (use {', '.join(refs)})")
    return refs[tag]


__all__ = ["ROOT", "load_config", "resolve", "model_paths", "final_dir", "data_dir", "model_ref"]
