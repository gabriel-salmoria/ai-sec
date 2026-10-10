"""Funde o adaptador LoRA ao Chandra e gera a versão FP8 (ambiente .venv-gpu).

    python -m ocr06.model.merge

1. models/<run>/merged/      Chandra BF16 + LoRA fundido (carregável no vLLM sem peft)
2. models/<run>/merged-fp8/  mesmo modelo quantizado em FP8_DYNAMIC com llm-compressor,
                             com a mesma receita do chandra-ocr-2-FP8-dynamic (config:
                             model.quant). FP8 dinâmico não precisa de dados de calibração.
"""
from __future__ import annotations

import argparse
import json

import torch

from . import load_config, model_paths


def main() -> None:
    from peft import PeftModel
    from transformers import AutoModelForImageTextToText, AutoProcessor

    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--skip-fp8", action="store_true")
    args = ap.parse_args()
    cfg = load_config(args.config)
    mc, paths = cfg["model"], model_paths(cfg)
    if not (paths["adapter"] / "adapter_config.json").exists():
        raise SystemExit(f"adaptador não encontrado em {paths['adapter']}; rode o treino antes")

    print(f"== fundindo LoRA ({paths['adapter']}) em {mc['base']}")
    processor = AutoProcessor.from_pretrained(paths["adapter"], trust_remote_code=True)
    model = AutoModelForImageTextToText.from_pretrained(mc["base"], dtype=torch.bfloat16,
                                                        trust_remote_code=True)
    model = PeftModel.from_pretrained(model, paths["adapter"]).merge_and_unload()
    model.save_pretrained(paths["merged"])
    processor.save_pretrained(paths["merged"])
    print(f"   salvo em {paths['merged']}")
    if args.skip_fp8:
        return

    from llmcompressor import oneshot
    from llmcompressor.modifiers.quantization import QuantizationModifier

    qc = mc["quant"]
    print(f"== quantizando em {qc['scheme']}")
    recipe = QuantizationModifier(targets="Linear", scheme=qc["scheme"], ignore=qc["ignore"])
    oneshot(model=model, recipe=recipe)
    model.save_pretrained(paths["merged_fp8"], save_compressed=True)
    processor.save_pretrained(paths["merged_fp8"])
    (paths["merged_fp8"] / "ocr06_quant.json").write_text(json.dumps(qc, indent=2))
    print(f"   salvo em {paths['merged_fp8']}")


if __name__ == "__main__":
    main()
