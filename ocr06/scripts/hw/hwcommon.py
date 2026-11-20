"""Shared helpers for the render_<generator>.py CLIs (stdlib + numpy + PIL only).

Job file: JSON lines, one job per line:
    {"id": str, "text": str, "style": int|str|null, "params": {...}}
Output per job: DIR/<id>.png (8-bit grayscale, dark ink on white, tightly
cropped with a small margin) and DIR/<id>.json with
    {"text", "generator", "style", "params", "seconds", "ok", "error", ...}.
"""
from __future__ import annotations

import json
import os
import re
import time
import traceback

import numpy as np
from PIL import Image

_ID_RE = re.compile(r"^[A-Za-z0-9._\-]+$")


def read_jobs(path: str) -> list[dict]:
    jobs = []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                j = json.loads(line)
            except json.JSONDecodeError as e:
                raise SystemExit(f"{path}:{n}: invalid JSON: {e}")
            jid = str(j.get("id", ""))
            if not _ID_RE.match(jid):
                raise SystemExit(f"{path}:{n}: bad or missing id {jid!r} (use [A-Za-z0-9._-])")
            j["id"] = jid
            j.setdefault("style", None)
            j["params"] = dict(j.get("params") or {})
            if not isinstance(j.get("text"), str):
                raise SystemExit(f"{path}:{n}: 'text' must be a string")
            jobs.append(j)
    ids = [j["id"] for j in jobs]
    if len(set(ids)) != len(ids):
        raise SystemExit(f"{path}: duplicate job ids")
    return jobs


def write_result(out_dir: str, job: dict, generator: str, img: Image.Image | None,
                 seconds: float, error: str | None = None, **extra) -> dict:
    ok = error is None and img is not None
    rec = {
        "text": job["text"], "generator": generator, "style": job.get("style"),
        "params": job.get("params", {}), "seconds": round(float(seconds), 4),
        "ok": ok, "error": None if ok else (error or "no image produced"),
    }
    rec.update(extra)
    png = os.path.join(out_dir, f"{job['id']}.png")
    if ok:
        img.save(png)
        rec["width"], rec["height"] = img.size
    elif os.path.exists(png):  # never leave a stale image next to a failed record
        os.remove(png)
    with open(os.path.join(out_dir, f"{job['id']}.json"), "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    return rec


def crop_ink(gray: np.ndarray, margin: int = 6, thresh: int = 200) -> np.ndarray:
    """Tight crop of a white-background uint8 image around pixels darker than thresh."""
    ys, xs = np.where(gray < thresh)
    if len(xs) == 0:
        return gray
    pad = np.pad(gray, margin, constant_values=255)
    return pad[ys.min():ys.max() + 2 * margin + 1, xs.min():xs.max() + 2 * margin + 1]


def fmt_exc(e: BaseException) -> str:
    return f"{type(e).__name__}: {e}"


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def tb() -> str:
    return traceback.format_exc(limit=3)
