"""CLI do pipeline OCR-06 (rode a partir da pasta ocr06/, ou use scripts/pipeline.sh).

    python -m ocr06 lexicon    # coleta IBGE/TSE/RFB e monta data/lexicon/
    python -m ocr06 fonts      # baixa fontes manuscritas e checa os acentos
    python -m ocr06 bressay    # baixa o BRESSAY, limpa as linhas e marca nomes
    python -m ocr06 generate   # gera o dataset sintético (imagens + labels.jsonl)
    python -m ocr06 mix        # junta sintético + BRESSAY em data/final/ (formato do VLM)
    python -m ocr06 exp1       # Experimento 1: validação do pipeline de dados
    python -m ocr06 all        # tudo acima, em ordem
"""
from __future__ import annotations

import argparse

from .common import load_config

STEPS = ("lexicon", "fonts", "bressay", "generate", "mix", "exp1")


def run(cmd: str, cfg: dict, args) -> None:
    name = getattr(args, "name", None) or cfg["generate"]["name"]
    if cmd == "lexicon":
        from .lexicon import build
        build(cfg)
    elif cmd == "fonts":
        from .fonts import fetch_fonts
        fetch_fonts(cfg)
    elif cmd == "bressay":
        from .bressay import build
        build(cfg)
    elif cmd == "generate":
        from .generate import generate
        generate(cfg, name=name, splits=getattr(args, "splits", None) or ["train", "val", "test"],
                 n=getattr(args, "n", None))
    elif cmd == "mix":
        from .mix import build
        build(cfg, name=name)
    elif cmd == "exp1":
        from .experiment1 import run as run_exp1
        run_exp1(cfg)


def main() -> None:
    ap = argparse.ArgumentParser(prog="ocr06")
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--workers", help="processos de geração (padrão: generate.workers)")
    ap.add_argument("--alpha", type=float, help="sobrescreve sampling.alpha")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for s in ("lexicon", "fonts", "bressay", "exp1"):
        sub.add_parser(s)
    g = sub.add_parser("generate")
    g.add_argument("--name", help="versão do dataset (padrão: generate.name)")
    g.add_argument("--splits", nargs="+")
    g.add_argument("--n", type=int, help="sobrescreve o nº de amostras de cada split")
    m = sub.add_parser("mix")
    m.add_argument("--name")
    a = sub.add_parser("all")
    a.add_argument("--name")
    args = ap.parse_args()

    cfg = load_config(args.config)
    if args.workers:
        cfg["generate"]["workers"] = args.workers
    if args.alpha is not None:
        cfg["sampling"]["alpha"] = args.alpha
    for cmd in (STEPS if args.cmd == "all" else (args.cmd,)):
        print(f"== {cmd}")
        run(cmd, cfg, args)


if __name__ == "__main__":
    main()
