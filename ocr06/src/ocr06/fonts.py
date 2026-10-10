"""Baixa fontes manuscritas do Google Fonts (licenças OFL/Apache) e valida acentos.

A API CSS do Google Fonts devolve URLs .ttf para clientes não-navegador.
Fontes sem algum glifo do português (ã, ç, é...) são descartadas, senão a imagem
teria "tofu" (caixas vazias) e o rótulo não bateria com o desenho.
"""
from __future__ import annotations

import re

import requests
from fontTools.ttLib import TTFont

from .common import assign_split, download, read_json, resolve, write_json

REQUIRED = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "áâãàéêíóôõúüçÁÂÃÀÉÊÍÓÔÕÚÜÇ"
    "':/-,."
)


def missing_glyphs(path) -> set[str]:
    cmap = TTFont(path).getBestCmap() or {}
    return {c for c in REQUIRED if ord(c) not in cmap}


def fetch_fonts(cfg: dict) -> dict:
    font_dir = resolve(cfg, "fonts")
    included, excluded = [], {}
    for family in cfg["fonts"]["families"]:
        slug = family.replace(" ", "")
        try:
            css = requests.get("https://fonts.googleapis.com/css2",
                               params={"family": family}, timeout=30)
            css.raise_for_status()
            urls = re.findall(r"url\((https://[^)]+\.ttf)\)", css.text)
            if not urls:
                excluded[family] = "sem .ttf na resposta"
                continue
            path = download(urls[0], font_dir / f"{slug}.ttf")
        except requests.RequestException as e:
            excluded[family] = f"download falhou: {e}"
            continue
        miss = missing_glyphs(path)
        if miss:
            excluded[family] = "faltam glifos: " + "".join(sorted(miss))
            path.unlink()
            continue
        included.append({"family": family, "file": path.name,
                         "split": "test" if assign_split(
                             {"test": cfg["fonts"]["font_holdout_frac"], "all": 1.0},
                             cfg["seed"], "font", family) == "test" else "all"})
    manifest = {"included": included, "excluded": excluded}
    write_json(font_dir / "manifest.json", manifest)
    print(f"  fontes válidas: {len(included)}; descartadas: {len(excluded)}")
    for fam, why in excluded.items():
        print(f"    - {fam}: {why}")
    return manifest


def fonts_for_split(cfg: dict, split: str) -> list[str]:
    """Fontes de teste exclusivas só aparecem no split test; as demais em todos."""
    font_dir = resolve(cfg, "fonts")
    manifest = read_json(font_dir / "manifest.json")
    paths = [str(font_dir / f["file"]) for f in manifest["included"]
             if f["split"] == "all" or split == "test"]
    if split == "test" and cfg["fonts"]["font_holdout_frac"] > 0:
        paths = [str(font_dir / f["file"]) for f in manifest["included"] if f["split"] == "test"]
    if not paths:
        raise RuntimeError("Nenhuma fonte disponível; rode `python -m ocr06 fonts` antes.")
    return paths
