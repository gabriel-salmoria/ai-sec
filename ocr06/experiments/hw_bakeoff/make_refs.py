"""Cut style-reference crops (real handwriting) out of BRESSAY pages.

Removes the ruled lines of the BRESSAY form (horizontal morphology + inpaint),
flattens the background and writes refs/<name>.png plus refs/refs.json with the
exact transcription of each crop (Emuru needs it). Run with .venv-hw-vatrpp.
"""
import json
import os

import cv2
import numpy as np

OCR06 = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PAGES = os.path.join(OCR06, "data", "pages", "bressay", "images")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "refs")

# name: (page, (x0, y0, x1, y1), transcription of the crop)
REFS = {
    "bressay_1631": ("1631-020.jpg", (8, 212, 596, 266), "nados às doenças mentais,"),
    "bressay_0675": ("0675-066.jpg", (13, 60, 690, 128), "ciedade brasileira era marcada pelo"),
    "bressay_7574": ("7574-030.jpg", (14, 88, 590, 143), "mo era o controle ideológico"),
}


def clean(gray: np.ndarray) -> np.ndarray:
    bg = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    bg = cv2.GaussianBlur(bg, (0, 0), 5)
    norm = np.clip(gray.astype(np.float32) / np.maximum(bg, 1) * 255.0, 0, 255).astype(np.uint8)
    ink = (norm < 200).astype(np.uint8)
    rule = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (81, 1)))
    rule = cv2.dilate(rule, np.ones((3, 1), np.uint8))
    out = cv2.inpaint(norm, rule * 255, 2, cv2.INPAINT_TELEA)
    out = np.where(out > 225, 255, out).astype(np.uint8)  # flatten paper
    ys, xs = np.where(out < 160)
    m = 4
    return out[max(ys.min() - m, 0):ys.max() + m + 1, max(xs.min() - m, 0):xs.max() + m + 1]


def main():
    os.makedirs(OUT, exist_ok=True)
    meta = {}
    for name, (page, box, text) in REFS.items():
        g = cv2.imread(os.path.join(PAGES, page), cv2.IMREAD_GRAYSCALE)
        x0, y0, x1, y1 = box
        crop = clean(g[y0:y1, x0:x1])
        path = os.path.join(OUT, f"{name}.png")
        cv2.imwrite(path, crop)
        meta[name] = {"image": f"refs/{name}.png", "text": text, "source": f"BRESSAY {page} box {box}"}
        print(name, crop.shape, text)
    # a clean synthetic pen line (Graves, style 3, bias 0.75, seed 1) as a 4th reference:
    # render_graves.py job {"text": "Maria da Silva", "style": 3, "params": {"bias": 0.75, "seed": 1}}
    if os.path.exists(os.path.join(OUT, "graves_style3.png")):
        meta["graves_style3"] = {"image": "refs/graves_style3.png", "text": "Maria da Silva",
                                 "source": "render_graves.py style 3 bias 0.75 seed 1"}
    with open(os.path.join(OUT, "refs.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
