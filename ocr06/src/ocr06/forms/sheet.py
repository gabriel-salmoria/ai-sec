"""Folhas de amostra para avaliar a dificuldade de leitura, no tamanho que o modelo vê.

    python -m ocr06.forms.sheet --name forms_amostra --out experiments/forms_amostra

Para cada nível: recortes dos campos escritos em escala 1:1 (página com lado maior de
2048 px, como entra no Chandra), com o texto esperado em cima; e duas páginas inteiras
reduzidas. Junto vão recortes de referência do OCRSD na mesma escala: fonte Caveat
(fácil demais para o Chandra) e escrita neural sjvasquez (onde o Chandra erra metade).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[3]
W = 1500


def _crop(im, box, pad=8, maxw=W // 2 - 20):
    x0, y0, x1, y1 = box
    c = im.crop((max(x0 - pad, 0), max(y0 - pad, 0), min(x1 + pad, im.width), min(y1 + pad, im.height)))
    if c.width > maxw:
        c = c.crop((0, 0, maxw, c.height))
    return c


def _grid(tiles, title):
    cols, colw = 2, W // 2
    rows = [tiles[i:i + cols] for i in range(0, len(tiles), cols)]
    H = 40 + sum(max(t.height for t in r) + 6 for r in rows)
    s = Image.new("RGB", (W, H), "white")
    ImageDraw.Draw(s).text((8, 10), title, fill="black")
    y = 40
    for r in rows:
        for j, t in enumerate(r):
            s.paste(t, (j * colw + 4, y))
        y += max(t.height for t in r) + 6
    return s


def _tile(crop, label):
    t = Image.new("RGB", (W // 2 - 10, crop.height + 18), "white")
    t.paste(crop, (0, 16))
    ImageDraw.Draw(t).text((2, 2), label[:95], fill=(200, 0, 0))
    return t


def ocrsd_reference(kind: str, n: int, rng) -> list[Image.Image]:
    rows = [json.loads(l) for l in open(ROOT / "data" / "pages" / "ocrsd" / "pages.jsonl", encoding="utf-8")]
    want = (lambda r: r["writing"] == "font" and "caveat" in r["batch"]) if kind == "caveat" else \
        (lambda r: r["writing"] == "sjvasquez")
    rows = [r for r in rows if want(r) and r["template"].startswith("certidao")]
    tiles = []
    for r in rng.permutation(len(rows))[:n]:
        r = rows[r]
        im = Image.open(ROOT / "data" / r["image"]).convert("RGB")
        if im.height < 2000:
            continue
        f = 2048 / max(im.size)
        im = im.resize((int(im.width * f), int(im.height * f)), Image.LANCZOS)
        fld = [x for x in r["fields"] if len(x["text"]) > 3]
        x = fld[int(rng.integers(len(fld)))]
        box = [int(v * f) for v in x["box"]]
        tiles.append(_tile(_crop(im, box), f"OCRSD {kind} | {x['text']}"))
    return tiles


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--per-level", type=int, default=16)
    a = ap.parse_args()
    out = ROOT / a.out
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    rows = [json.loads(l) for l in open(ROOT / "data" / "pages" / a.name / "pages.jsonl", encoding="utf-8")]
    ref = _grid(ocrsd_reference("caveat", 8, rng) + ocrsd_reference("sjvasquez", 8, rng),
                "REFERENCIA (mesma escala): OCRSD Caveat (Chandra le ~96%) e OCRSD neural sjvasquez (Chandra le ~47%)")
    ref.save(out / "0_referencia_ocrsd.jpg", quality=92)
    for level in sorted({r["level"] for r in rows}):
        rs = [r for r in rows if r["level"] == level]
        tiles = []
        for r in rs:
            im = Image.open(ROOT / "data" / r["image"]).convert("RGB")
            fl = [f for f in r["fields"] if f["hand"] != "mark" and len(f["text"]) > 2]
            for k in rng.permutation(len(fl))[:3]:
                f = fl[k]
                w = r["writer"]
                who = w.get("font") or f"{w['hand']} estilo {w.get('style')}"
                tiles.append(_tile(_crop(im, f["box"]), f"{who} [{f['cls']}] {f['text']}"))
        _grid(tiles[:a.per_level * 2], f"NIVEL {level}: campos na escala do modelo (texto esperado em vermelho)") \
            .save(out / f"nivel{level}_campos.jpg", quality=92)
        pages = [Image.open(ROOT / "data" / r["image"]).convert("RGB") for r in rs[:2]]
        for p in pages:
            p.thumbnail((W // 2, 2000))
        s = Image.new("RGB", (W, max(p.height for p in pages)), "white")
        for j, p in enumerate(pages):
            s.paste(p, (j * W // 2, 0))
        s.save(out / f"nivel{level}_paginas.jpg", quality=88)
    print("folhas em", out)


if __name__ == "__main__":
    main()
