"""Build the comparison sheets and a timing summary from out/<generator>/.

sheet.jpg            rows = test strings + probes, columns = generator/style (all 12)
sheet_<gen>.jpg      same rows, one generator, larger cells (for inspection)
graves_styles.jpg    the 13 Graves priming styles on one string
graves_bias.jpg      Graves bias sweep (unprimed and style 3)
summary.json         ok counts and seconds per line per generator
Run with any venv that has Pillow + numpy (e.g. .venv-hw-vatrpp).
"""
import json
import os
import statistics

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
META = json.load(open(os.path.join(HERE, "jobs", "rows.json"), encoding="utf-8"))
ROWS, COLS = META["rows"], META["columns"]


def font(size):
    for p in ["/usr/share/fonts/TTF/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf",
              "/usr/share/fonts/noto/NotoSans-Regular.ttf"]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def load(gen, jid):
    js = os.path.join(OUT, gen, jid + ".json")
    if not os.path.exists(js):
        return None, None
    rec = json.load(open(js, encoding="utf-8"))
    png = os.path.join(OUT, gen, jid + ".png")
    img = Image.open(png).convert("L") if rec["ok"] and os.path.exists(png) else None
    return rec, img


def fit(img, h, wmax):
    s = h / img.height
    if img.width * s > wmax:
        s = wmax / img.width
    return img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.LANCZOS)


def cell(gen, col, r, h, w, f_small):
    jid = f"{gen}_{col}_r{r:02d}"
    rec, img = load(gen, jid)
    c = Image.new("L", (w, h + 18), 255)
    d = ImageDraw.Draw(c)
    if img is not None:
        c.paste(fit(img, h, w - 8), (4, 0))
        return c
    fold_rec, fold_img = load(gen, jid + "_fold")
    if fold_img is not None:  # Graves: show what the accent-folded text gives
        c.paste(fit(fold_img, h - 14, w - 8), (4, 14))
        d.text((4, 0), "REJECTED; folded: " + fold_rec["text"], fill=0, font=f_small)
        return c
    msg = "missing" if rec is None else (rec["error"] or "failed")
    d.text((4, 4), "FAILED", fill=0, font=f_small)
    d.text((4, 20), msg[:70], fill=90, font=f_small)
    d.text((4, 34), msg[70:140], fill=90, font=f_small)
    return c


def sheet(gens, path, h=56, w=430, label_w=330):
    f_big, f_small = font(16), font(11)
    cols = [(g, c) for g in gens for c in COLS[g]]
    W = label_w + w * len(cols)
    rh = h + 22
    H = 44 + rh * len(ROWS)
    S = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(S)
    for k, (g, c) in enumerate(cols):
        x = label_w + k * w
        d.text((x + 4, 4), g, fill=0, font=f_big)
        d.text((x + 4, 24), c, fill=60, font=f_small)
        d.line([(x, 0), (x, H)], fill=180)
    for r, text in enumerate(ROWS):
        y = 44 + r * rh
        d.line([(0, y), (W, y)], fill=180)
        d.text((4, y + h // 2 - 8), text, fill=0, font=f_big if len(text) < 32 else f_small)
        for k, (g, c) in enumerate(cols):
            S.paste(cell(g, c, r, h, w, f_small), (label_w + k * w + 1, y + 2))
    S.convert("RGB").save(path, quality=88)
    print(path, S.size)


def strip(ids, gen, labels, path, h=80, w=1300):
    f = font(14)
    S = Image.new("L", (w + 220, (h + 8) * len(ids)), 255)
    d = ImageDraw.Draw(S)
    for k, (jid, lab) in enumerate(zip(ids, labels)):
        rec, img = load(gen, jid)
        y = k * (h + 8)
        d.text((4, y + h // 2 - 8), lab, fill=0, font=f)
        if img is not None:
            S.paste(fit(img, h, w), (220, y))
        else:
            d.text((220, y + h // 2 - 8), "FAILED: " + (rec["error"] if rec else "missing"), fill=0, font=f)
    S.convert("RGB").save(path, quality=88)
    print(path, S.size)


def summary():
    res = {}
    for gen in ["graves", "vatrpp", "emuru", "emuru_cpu"]:
        d = os.path.join(OUT, gen)
        if not os.path.isdir(d):
            continue
        recs = [json.load(open(os.path.join(d, f), encoding="utf-8")) for f in sorted(os.listdir(d))
                if f.endswith(".json")]
        ok = [r for r in recs if r["ok"]]
        secs = [r["seconds"] for r in ok]
        hs = [r["height"] for r in ok]
        res[gen] = {
            "jobs": len(recs), "ok": len(ok),
            "failed_charset": sum(1 for r in recs if not r["ok"] and "outside" in (r["error"] or "")),
            "failed_other": [(r["text"], r.get("style_used", r["style"]), r["error"]) for r in recs
                             if not r["ok"] and "outside" not in (r["error"] or "")],
            "sec_per_line_median": round(statistics.median(secs), 3) if secs else None,
            "sec_per_line_mean": round(statistics.mean(secs), 3) if secs else None,
            "height_px_median": statistics.median(hs) if hs else None,
            "device": sorted({r.get("device") for r in ok}),
        }
    with open(os.path.join(HERE, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    sheet(["graves", "vatrpp", "emuru"], os.path.join(HERE, "sheet.jpg"))
    for g in ["graves", "vatrpp", "emuru"]:
        sheet([g], os.path.join(HERE, f"sheet_{g}.jpg"), h=90, w=760, label_w=360)
    strip([f"graves_allstyles_s{s:02d}" for s in range(13)], "graves",
          [f"style {s}" for s in range(13)], os.path.join(HERE, "graves_styles.jpg"))
    ids, labs = [], []
    for st in ["none", "3"]:
        for b in [0.1, 0.3, 0.5, 0.75, 1.0, 2.0]:
            ids.append(f"graves_bias_{st}_{b}")
            labs.append(f"{'unprimed' if st == 'none' else 'style 3'}  bias {b}")
    strip(ids, "graves", labs, os.path.join(HERE, "graves_bias.jpg"), h=70)
    summary()
