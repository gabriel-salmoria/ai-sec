#!/usr/bin/env python
"""Batch renderer for the Graves/sjvasquez handwriting model (NumPy port, CPU).

    .venv-hw-graves/bin/python scripts/hw/render_graves.py --jobs jobs.jsonl --out DIR

Job: {"id": str, "text": str, "style": int 0-12 | null, "params": {...}}
  style   priming writer of the original repo (0-12); null = unprimed (random hand)
  params  bias      0.1-1.0 neatness (default 0.75; higher = neater)
          seed      int (default: crc32 of the id)
          scale     px per model unit (default 5.0 -> ~100-140 px per line)
          pen_width px at output resolution (default 3.0)
          pressure  0-1 width variation from pen speed + start/end taper (default 0.4)
          ink       0-1 ink darkness (default 1.0)
          slant     extra shear in degrees, positive leans right (default 0)
          prime_npy / prime_text   custom priming: an (N,3) offsets array in the
                    IAM-OnDB format of styles/*.npy plus the text it writes
          retries   extra attempts if sampling stops before the end of the text (default 2)
Outputs: DIR/<id>.png (grayscale, dark ink on white), DIR/<id>.json, and
DIR/<id>.npy = float32 (N,3) [x_px, y_px, pen_up] in the PNG's pixel frame
(y down, pen_up=1 on the last point of each stroke) for re-rendering.
Texts outside the model alphabet (no accents, no Q/X/Z, no /, ...) fail with ok=false.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import zlib

os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
os.environ.setdefault("OMP_NUM_THREADS", "4")

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402
from scipy.signal import savgol_filter  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import graves_np as G  # noqa: E402
import hwcommon as hc  # noqa: E402

OCR06 = os.path.abspath(os.path.join(HERE, "..", ".."))
STYLE_DIR = os.path.join(OCR06, "third_party", "sjvasquez", "styles")
CKPT = os.path.join(OCR06, "third_party", "sjvasquez", "checkpoints", "model-17900")
NPZ = os.path.join(OCR06, "third_party", "graves_np", "model-17900.npz")
GENERATOR = "graves_sjvasquez"
N_STYLES = 13

DEFAULTS = dict(bias=0.75, scale=5.0, pen_width=3.0, pressure=0.4, ink=1.0, slant=0.0, retries=2)


# ---------------------------------------------------------------- strokes ---
def offsets_to_coords(off):
    return np.concatenate([np.cumsum(off[:, :2], axis=0), off[:, 2:3]], axis=1)


def split_strokes(coords):
    return [s for s in np.split(coords, np.where(coords[:, 2] == 1)[0] + 1) if len(s)]


def denoise(coords):
    out = []
    for s in split_strokes(coords):
        if len(s) >= 3:
            s = s.copy()
            win = min(7, len(s) if len(s) % 2 else len(s) - 1)
            if win >= 5:
                s[:, 0] = savgol_filter(s[:, 0], win, 3, mode="nearest")
                s[:, 1] = savgol_filter(s[:, 1], win, 3, mode="nearest")
        out.append(s)
    return np.vstack(out)


def align(coords):
    """Remove global baseline slope (as in the original drawing.align)."""
    c = coords.copy()
    x = np.stack([np.ones(len(c)), c[:, 0]], 1)
    offset, slope = np.linalg.lstsq(x, c[:, 1], rcond=None)[0]
    th = np.arctan(slope)
    R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
    c[:, :2] = c[:, :2] @ R - offset
    return c


def to_pixels(off, scale, slant_deg, margin):
    c = align(denoise(offsets_to_coords(off.astype(np.float64))))
    if slant_deg:
        c[:, 0] += np.tan(np.radians(slant_deg)) * c[:, 1]
    c[:, :2] *= scale
    c[:, 1] *= -1.0  # model y is up, image y is down
    c[:, :2] -= c[:, :2].min(0) - margin
    return c


# --------------------------------------------------------------- drawing ----
def render(coords, pen_width, pressure, ink, rng, ss=4):
    """Rasterise strokes with per-point widths, 4x supersampled, white bg."""
    W = int(np.ceil(coords[:, 0].max() + coords[:, 0].min()))
    H = int(np.ceil(coords[:, 1].max() + coords[:, 1].min()))
    can = Image.new("L", (W * ss, H * ss), 0)
    d = ImageDraw.Draw(can)
    strokes = split_strokes(coords)
    seglens = np.concatenate([np.linalg.norm(np.diff(s[:, :2], axis=0), axis=1)
                              for s in strokes if len(s) > 1] or [np.ones(1)])
    med = max(float(np.median(seglens)), 1e-6)
    for s in strokes:
        P = s[:, :2] * ss
        n = len(P)
        if n == 1:
            r = pen_width * ss / 2
            d.ellipse([P[0, 0] - r, P[0, 1] - r, P[0, 0] + r, P[0, 1] + r], fill=255)
            continue
        seg = np.linalg.norm(np.diff(s[:, :2], axis=0), axis=1)
        speed = np.concatenate([[seg[0]], (seg[1:] + seg[:-1]) / 2, [seg[-1]]]) / med
        f = 1.0 - 0.45 * pressure * np.tanh(speed - 1.0)          # fast = thinner
        drift = np.cumsum(rng.normal(0, 1, n)) / np.sqrt(np.arange(1, n + 1))
        f *= 1.0 + 0.10 * pressure * np.clip(drift, -2, 2)        # slow pressure drift
        k = np.arange(n)
        taper = np.minimum(1.0, 0.45 + 0.18 * np.minimum(k, n - 1 - k))
        f *= taper ** pressure                                    # pen lands / lifts
        w = np.maximum(pen_width * f, 0.6) * ss
        for i in range(n - 1):
            d.line([tuple(P[i]), tuple(P[i + 1])], fill=255,
                   width=max(1, int(round((w[i] + w[i + 1]) / 2))))
        for i in range(n):
            r = w[i] / 2
            d.ellipse([P[i, 0] - r, P[i, 1] - r, P[i, 0] + r, P[i, 1] + r], fill=255)
    cov = np.asarray(can.resize((W, H), Image.BOX), np.float32) / 255.0
    return Image.fromarray((255.0 - 255.0 * ink * cov).round().astype(np.uint8), "L")


# ---------------------------------------------------------------- jobs ------
def load_style(style):
    s = int(style)
    if not 0 <= s < N_STYLES:
        raise ValueError(f"style must be 0..{N_STYLES - 1} or null, got {style!r}")
    strokes = np.load(os.path.join(STYLE_DIR, f"style-{s}-strokes.npy")).astype(np.float32)
    chars = np.load(os.path.join(STYLE_DIR, f"style-{s}-chars.npy")).tobytes().decode("utf-8")
    return strokes, chars


def prepare(job):
    """Validate a job; returns dict with everything the sampler needs, or raises."""
    text = job["text"]
    p = {**DEFAULTS, **job["params"]}
    if not text.strip():
        raise ValueError("empty text")
    if len(text) > G.MAX_CHARS:
        raise ValueError(f"text has {len(text)} chars; max {G.MAX_CHARS} per call")
    G.encode(text)  # raises on characters outside the alphabet
    bias = float(p["bias"])
    if not 0.0 <= bias <= 10.0:
        raise ValueError(f"bias out of range: {bias}")
    prime = None
    if p.get("prime_npy"):
        prime = (np.load(p["prime_npy"]).astype(np.float32), str(p["prime_text"]))
        G.encode(prime[1])
    elif job.get("style") is not None:
        prime = load_style(job["style"])
    seed = p.get("seed")
    seed = int(seed) if seed is not None else zlib.crc32(job["id"].encode())
    return dict(job=job, text=text, bias=bias, prime=prime, seed=seed, p=p)


def make_image(item, off):
    p = item["p"]
    margin = float(p["pen_width"]) + 6.0
    coords = to_pixels(off, float(p["scale"]), float(p["slant"]), margin)
    img = render(coords, float(p["pen_width"]), float(p["pressure"]), float(p["ink"]),
                 np.random.default_rng(item["seed"] + 1))
    return coords.astype(np.float32), img


def run_batch(model, items, out_dir, steps_per_char):
    """Sample a batch; incomplete samples are retried with derived seeds."""
    t0 = time.time()
    pending = list(items)
    attempt = {id(it): 0 for it in items}
    results = {}
    while pending:
        seeds = [it["seed"] + 7919 * attempt[id(it)] for it in pending]
        res = model.sample([it["text"] for it in pending], [it["bias"] for it in pending],
                           seeds, [it["prime"] for it in pending], steps_per_char)
        nxt = []
        for it, (off, ci) in zip(pending, res):
            done = len(ci) > 0 and ci.max() >= len(it["text"]) and \
                len(off) < steps_per_char * len(it["text"])
            attempt[id(it)] += 1
            if done or attempt[id(it)] > int(it["p"]["retries"]):
                results[id(it)] = (off, ci, done, it["seed"] + 7919 * (attempt[id(it)] - 1))
            else:
                nxt.append(it)
        pending = nxt
    per = (time.time() - t0) / len(items)
    for it in items:
        off, ci, done, used_seed = results[id(it)]
        npy = os.path.join(out_dir, f"{it['job']['id']}.npy")
        t1 = time.time()
        try:
            if not done:
                raise RuntimeError("sampling stopped before the end of the text "
                                   f"(attention reached char {int(ci.max()) if len(ci) else -1} "
                                   f"of {len(it['text'])}) after {attempt[id(it)]} attempts")
            coords, img = make_image(it, off)
            np.save(npy, coords)
            hc.write_result(out_dir, it["job"], GENERATOR, img, per + time.time() - t1, None,
                            device="cpu", seed=it["seed"], sample_seed=used_seed,
                            attempts=attempt[id(it)], n_points=int(len(off)))
        except Exception as e:  # noqa: BLE001
            if os.path.exists(npy):
                os.remove(npy)
            hc.write_result(out_dir, it["job"], GENERATOR, None, per, hc.fmt_exc(e),
                            seed=it["seed"], attempts=attempt[id(it)])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jobs", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--steps-per-char", type=int, default=60)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    jobs = hc.read_jobs(args.jobs)
    model = G.GravesNP(G.load_weights(NPZ, CKPT))
    items = []
    for j in jobs:
        try:
            items.append(prepare(j))
        except Exception as e:  # noqa: BLE001
            hc.write_result(args.out, j, GENERATOR, None, 0.0, hc.fmt_exc(e))
            hc.log(f"[{j['id']}] rejected: {e}")
    items.sort(key=lambda it: -len(it["text"]))
    t0 = time.time()
    for b in range(0, len(items), args.batch_size):
        batch = items[b:b + args.batch_size]
        try:
            run_batch(model, batch, args.out, args.steps_per_char)
        except Exception:  # noqa: BLE001  -> fall back to one job at a time
            hc.log("batch failed, retrying jobs one by one:\n" + hc.tb())
            for it in batch:
                try:
                    run_batch(model, [it], args.out, args.steps_per_char)
                except Exception as e:  # noqa: BLE001
                    hc.write_result(args.out, it["job"], GENERATOR, None, 0.0, hc.fmt_exc(e))
        hc.log(f"{min(b + args.batch_size, len(items))}/{len(items)} sampled "
               f"({time.time() - t0:.1f}s)")
    n_ok = sum(1 for j in jobs if os.path.exists(os.path.join(args.out, j["id"] + ".png")))
    hc.log(f"done: {n_ok}/{len(jobs)} ok -> {args.out}")


if __name__ == "__main__":
    main()
