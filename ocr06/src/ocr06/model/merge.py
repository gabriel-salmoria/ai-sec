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

from . import ROOT, load_config, model_paths


def main() -> None:
    from peft import PeftModel
    from transformers import AutoModelForImageTextToText, AutoProcessor

    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--skip-fp8", action="store_true")
    ap.add_argument("--int4", action="store_true",
                    help="também gera INT4 só nos pesos (W4A16, arredondamento simples, sem dados)")
    ap.add_argument("--skip-merge", action="store_true", help="usa o models/<run>/merged já salvo")
    ap.add_argument("--base-only", action="store_true",
                    help="só quantiza o Chandra base em FP8 (mesma receita), em models/base_fp8")
    args = ap.parse_args()
    cfg = load_config(args.config)
    mc, paths = cfg["model"], model_paths(cfg)
    if args.base_only:
        from llmcompressor import oneshot
        from llmcompressor.modifiers.quantization import QuantizationModifier
        out = ROOT / "models" / "base_fp8"
        processor = AutoProcessor.from_pretrained(mc["base"], trust_remote_code=True)
        model = AutoModelForImageTextToText.from_pretrained(mc["base"], dtype=torch.bfloat16,
                                                            trust_remote_code=True)
        qc = mc["quant"]
        print(f"== quantizando o base em {qc['scheme']}")
        oneshot(model=model, recipe=QuantizationModifier(targets="Linear", scheme=qc["scheme"],
                                                         ignore=qc["ignore"]))
        model.save_pretrained(out, save_compressed=True)
        processor.save_pretrained(out)
        (out / "ocr06_quant.json").write_text(json.dumps(qc, indent=2))
        print(f"   salvo em {out}")
        return
    if not (paths["adapter"] / "adapter_config.json").exists():
        raise SystemExit(f"adaptador não encontrado em {paths['adapter']}; rode o treino antes")

    processor = AutoProcessor.from_pretrained(paths["adapter"], trust_remote_code=True)
    if args.skip_merge:
        model = AutoModelForImageTextToText.from_pretrained(paths["merged"], dtype=torch.bfloat16,
                                                            trust_remote_code=True)
    else:
        print(f"== fundindo LoRA ({paths['adapter']}) em {mc['base']}")
        model = AutoModelForImageTextToText.from_pretrained(mc["base"], dtype=torch.bfloat16,
                                                            trust_remote_code=True)
        model = PeftModel.from_pretrained(model, paths["adapter"]).merge_and_unload()
        model.save_pretrained(paths["merged"])
        processor.save_pretrained(paths["merged"])
        print(f"   salvo em {paths['merged']}")
    if args.skip_fp8:
        if args.int4:
            quant_int4(model, processor, mc, paths)
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
    if args.int4:  # o FP8 alterou o modelo na memória: recarrega o BF16 fundido
        model = AutoModelForImageTextToText.from_pretrained(paths["merged"], dtype=torch.bfloat16,
                                                            trust_remote_code=True)
        quant_int4(model, processor, mc, paths)


def quant_int4(model, processor, mc, paths) -> None:
    """INT4 só nos pesos (W4A16), por arredondamento simples: não usa dados de calibração.
    Mesmas camadas ignoradas do FP8 (visão, atenção linear, lm_head). Roda no vLLM com os
    kernels Marlin (qualquer GPU a partir da A100, inclusive L4/L40S)."""
    from llmcompressor import oneshot
    from llmcompressor.modifiers.quantization import QuantizationModifier
    qc = dict(mc["quant"], scheme="W4A16")
    print("== quantizando em W4A16 (INT4, sem calibração)")
    oneshot(model=model, recipe=QuantizationModifier(targets="Linear", scheme="W4A16", ignore=qc["ignore"]))
    model.save_pretrained(paths["merged_int4"], save_compressed=True)
    processor.save_pretrained(paths["merged_int4"])
    (paths["merged_int4"] / "ocr06_quant.json").write_text(json.dumps(qc, indent=2))
    print(f"   salvo em {paths['merged_int4']}")


if __name__ == "__main__":
    main()
