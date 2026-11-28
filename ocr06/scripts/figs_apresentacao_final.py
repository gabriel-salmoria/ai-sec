"""Figures for the final presentation (apresentacoes/2026-11-17_resultados/figs): results bar chart, name crops
with each model's reading, and one test page with the name box drawn.

    .venv/bin/python scripts/figs_apresentacao_final.py
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ocr06.evaluate import normalize  # noqa: E402
from ocr06.pages_eval import MARGIN, fields_of, infix_span, overlaps, page_size, parse_blocks  # noqa: E402

OUT = ROOT.parent / "apresentacoes" / "2026-11-17_resultados" / "figs"
OUT.mkdir(parents=True, exist_ok=True)
P = ROOT / "experiments" / "paginas"
DATA = ROOT / "data"
COLORS = {"Chandra (base)": "#2a78d6", "lora_v1": "#eb6834", "lora_v2": "#1baf7a"}  # validated, fixed order
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"


CLASSES = [("todos", "Todos os campos"), ("name", "Nomes"), ("date", "Datas"), ("number", "Números"),
           ("closed", "Opções fixas"), ("place", "Lugares"), ("text", "Texto livre")]


def summary(set_name: str, models: list[str]) -> dict:
    """Exact match (local) per field class, plus the field count of each class."""
    res = json.load(open(P / f"avaliacao_{set_name}.json"))["resumo"]
    out, n = {}, {}
    for m in models:
        s = res[m]
        out[m] = {"todos": 100 * s["todos"]["exato_local"],
                  **{k: 100 * v["exato_local"] for k, v in s["por_classe"].items()}}
        n = {"todos": s["todos"]["campos"], **{k: v["campos"] for k, v in s["por_classe"].items()}}
    return out, n


def chart() -> None:
    keys = ["base_g4", "lora_v1", "lora_v2"]
    labels = list(COLORS)
    fig, axes = plt.subplots(2, 1, figsize=(10.4, 5.6), sharey=True)
    fig.patch.set_facecolor("#fafafa")
    for ax, (title, set_name) in zip(axes, [("Teste difícil (100 páginas, 70% das palavras de nome nunca vistas)", "teste_local"),
                                            ("Teste normal (100 páginas, nomes pela frequência real)", "forms_v2_normal")]):
        d, n = summary(set_name, keys)
        ax.set_facecolor("#fafafa")
        w, gap = 0.27, 0.02
        for i, (lab, key) in enumerate(zip(labels, keys)):
            for g, (cls, _) in enumerate(CLASSES):
                x = g + (i - 1) * (w + gap)
                v = d[key][cls]
                ax.bar(x, v, w, color=COLORS[lab], label=lab if g == 0 else None, zorder=2)
                ax.text(x, v + 1.5, f"{v:.0f}", ha="center", va="bottom", fontsize=7.5, color=INK)
        ax.axvline(0.5, color=GRID, lw=1.2, zorder=1)
        ax.set_xticks(range(len(CLASSES)), [f"{name}\n({n[c]})" for c, name in CLASSES], fontsize=8.5, color=INK)
        ax.set_title(title, fontsize=9.5, color=INK, loc="left")
        ax.set_ylim(0, 108)
        ax.set_yticks([0, 25, 50, 75, 100])
        ax.yaxis.grid(True, color=GRID, lw=0.8, zorder=0)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.spines["bottom"].set_color(INK2)
        ax.tick_params(axis="y", colors=INK2, labelsize=8, length=0)
        ax.tick_params(axis="x", length=0)
        ax.set_ylabel("Acerto exato (%)", color=INK2, fontsize=8.5)
    handles, lab = axes[0].get_legend_handles_labels()
    fig.legend(handles, lab, loc="upper center", ncol=3, frameon=False, fontsize=9.5, bbox_to_anchor=(0.5, 1.0))
    fig.tight_layout(rect=(0, 0, 1, 0.95), h_pad=1.2)
    fig.savefig(OUT / "resultados.pdf")
    plt.close(fig)


def reading(text: str, field) -> str:
    """Model reading at the field: closest stretch to the gold value, widened to whole words."""
    blocks = parse_blocks(text)
    hay = " ".join(b.text for b in blocks if overlaps(b.bbox, field.box, MARGIN))
    _, s, e = infix_span(field.cmp, hay)
    while s > 0 and hay[s - 1] not in " \n":
        s -= 1
    while e < len(hay) and hay[e] not in " \n,.;":
        e += 1
    return hay[s:e].strip()


def crops() -> None:
    examples = [("forms_v1_00925", "Claudemar Reis Scalabrin"), ("forms_v1_00394", "Reni Oppermann Manetti Guiao"),
                ("forms_v1_00153", "Maikon Giordano Cirino"), ("forms_v1_00572", "Guiomar Schiavon Arrabal")]
    gold = {json.loads(l)["id"]: json.loads(l) for l in open(DATA / "pages" / "teste_local" / "pages.jsonl")}
    preds = {m: {json.loads(l)["id"]: json.loads(l)["pred"] for l in open(P / m / "teste_local.jsonl")}
             for m in ("base_g4", "lora_v2")}
    info = []
    for k, (pid, name) in enumerate(examples, 1):
        g = gold[pid]
        raw = next(f for f in g["fields"] if f.get("text") == name)
        fld = next(f for f in fields_of(g, page_size(g, DATA)) if f.cmp == normalize(name))
        x0, y0, x1, y1 = raw["box"]
        im = Image.open(DATA / g["image"]).convert("RGB")
        pad = 12
        im.crop((max(0, x0 - pad), max(0, y0 - pad), x1 + pad, y1 + pad)).save(OUT / f"nome_{k}.png")
        info.append({"arquivo": f"nome_{k}.png", "gabarito": name,
                     "base": reading(preds["base_g4"][pid], fld), "lora_v2": reading(preds["lora_v2"][pid], fld)})
        if k == 1:  # page thumbnail with the field box
            th = im.copy()
            ImageDraw.Draw(th).rectangle((x0 - 8, y0 - 8, x1 + 8, y1 + 8), outline=(235, 104, 52), width=8)
            th.thumbnail((900, 1200))
            th.save(OUT / "pagina_exemplo.jpg", quality=90)
    (OUT / "nomes.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in info:
        print(r)


def generator() -> None:
    """Clean test page (no box) and zoomed regions, for the generator slide."""
    im = Image.open(DATA / "pages" / "teste_local" / "images" / "forms_v1_00925.jpg").convert("RGB")
    th = im.copy()
    th.thumbnail((900, 1200))
    th.save(OUT / "gerador_pagina.jpg", quality=90)
    regions = {  # px boxes on the 1512 x 2048 page
        "gerador_zoom_1.jpg": (110, 515, 1385, 988),   # matrícula até genitores e médico
        "gerador_zoom_2.jpg": (110, 1306, 1440, 1580),  # CNS, oficial, local e data de emissão, escrevente, cargo
    }
    for old in OUT.glob("gerador_zoom_*.jpg"):
        old.unlink()
    for name, box in regions.items():
        im.crop(box).save(OUT / name, quality=92)


def demo(pid: str = "forms_v1_00925", model: str = "lora_v2") -> None:
    """Model output redrawn on a blank page: each block's text at its box, handwritten fields in
    green (exact) or red (wrong), printed text in gray. Same page as gerador_pagina.jpg."""  # noqa: E501
    from PIL import ImageFont
    from ocr06.pages_eval import compact
    g = next(json.loads(l) for l in open(DATA / "pages" / "teste_local" / "pages.jsonl") if f'"{pid}"' in l)
    pred = next(json.loads(l)["pred"] for l in open(P / model / "teste_local.jsonl") if f'"{pid}"' in l)
    blocks = parse_blocks(pred)
    W, H = Image.open(DATA / g["image"]).size
    color = {}
    ok_n = tot = 0
    for f in fields_of(g, page_size(g, DATA)):
        if f.stripped or f.short or f.box is None:
            continue
        near = [i for i, b in enumerate(blocks) if overlaps(b.bbox, f.box, MARGIN)]
        prep = compact if f.cls == "number" else (lambda s: s)
        hay = prep(" ".join(blocks[i].text for i in near))
        ok = infix_span(f.cmp, hay)[0] == 0
        tot, ok_n = tot + 1, ok_n + ok
        if near:
            best = min(near, key=lambda i: infix_span(f.cmp, prep(normalize(blocks[i].text)))[0])
            color[best] = "#1b8a62" if ok else "#c0392b"
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    reg, bold = "/usr/share/fonts/noto/NotoSans-Regular.ttf", "/usr/share/fonts/noto/NotoSans-Bold.ttf"
    for i, b in enumerate(blocks):
        x0, y0, x1, y1 = (b.bbox[0] * W / 1000, b.bbox[1] * H / 1000, b.bbox[2] * W / 1000, b.bbox[3] * H / 1000)
        if not b.text.strip():
            d.rectangle((x0, y0, x1, y1), fill="#ececec", outline="#c8c8c8", width=2)
            continue
        d.rectangle((x0, y0, x1, y1), outline="#d6d6d6", width=2)
        size = max(10, int((y1 - y0) * 0.8))
        font = ImageFont.truetype(bold if i in color else reg, size)
        while size > 10 and d.textlength(b.text, font=font) > (x1 - x0) * 1.05:
            size -= 1
            font = ImageFont.truetype(bold if i in color else reg, size)
        d.text((x0 + 2, (y0 + y1) / 2), b.text, fill=color.get(i, "#6b6a66"), font=font, anchor="lm")
    im.thumbnail((900, 1200))
    im.save(OUT / f"demo_{model}.png")
    print(f"demo {pid} {model}: {ok_n}/{tot} campos exatos")


if __name__ == "__main__":
    chart()
    crops()
    generator()
    demo()
    demo(model="base_g4")
