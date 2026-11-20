#!/usr/bin/env python
"""Batch renderer for VATr++ (blowing-up-groundhogs/vatrpp, MIT), GPU if available.

    .venv-hw-vatrpp/bin/python scripts/hw/render_vatrpp.py --jobs jobs.jsonl --out DIR

Job: {"id": str, "text": str, "style": int | str | null, "params": {...}}
  style   int  = IAM test writer (index into the sorted writer ids of files/IAM-32.pickle)
          str  = name in --refs-json, or a path to an image (a line, cut into 192-px
                 chunks as in the HF README) or to a folder of word images
          null = IAM test writer picked from the seed
  params  refs          list of image paths; overrides style (1 path = line, >1 = words)
          seed          int, picks the 15 reference words / chunks (default crc32(id))
          mode          "words" (default: one query per word, baseline-stitched, as in the
                        paper) or "line" (whole line as one query)
          upscale       output scale factor from the native 32-px height (default 4)
          allow_unseen  true = also accept characters outside the 80-char training
                        alphabet (accents etc.), using their Unifont glyphs zero-shot.
                        Off by default because they mostly come out wrong (see report).
Output: DIR/<id>.png (grayscale on white, cropped), DIR/<id>.json.
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import random
import sys
import time
import zlib

import numpy as np
import torch
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hwcommon as hc  # noqa: E402

OCR06 = os.path.abspath(os.path.join(HERE, "..", ".."))
TP = os.path.join(OCR06, "third_party")
VD = os.path.join(TP, "vatrpp")
DEFAULT_REFS = os.path.join(OCR06, "experiments", "hw_bakeoff", "refs", "refs.json")
GENERATOR = "vatrpp"
# extra characters given Unifont query glyphs (only used with allow_unseen)
UNSEEN = "áâãàéêíóôõúüçÁÂÃÀÉÊÍÓÔÕÚÜÇºª°"
DEFAULTS = dict(mode="words", upscale=4, allow_unseen=False)


def _patch_hub():
    """The HF code fetches its own files from the Hub; serve them from the local clone."""
    import huggingface_hub
    orig = huggingface_hub.hf_hub_download

    def local(repo_id=None, filename=None, **kw):
        if repo_id == "blowing-up-groundhogs/vatrpp":
            p = os.path.join(VD, filename)
            if os.path.exists(p):
                return p
        return orig(repo_id=repo_id, filename=filename, **kw)
    huggingface_hub.hf_hub_download = local


class VATrRunner:
    def __init__(self, device):
        _patch_hub()
        sys.path.insert(0, TP)
        from vatrpp import VATrPP  # noqa: E402
        from torchvision import transforms as T
        cfg_special = json.load(open(os.path.join(VD, "config.json")))["special_alphabet"]
        self.wrapper = VATrPP.from_pretrained(VD, local_files_only=True, device=device,
                                              special_alphabet=cfg_special + UNSEEN)
        self.wrapper.to(device).eval()
        self.m = self.wrapper.model
        self.device = device
        self.trained = set(self.m.args.alphabet)
        self.extended = self.trained | set(UNSEEN)
        self.tf = T.Compose([T.ToTensor(), T.Normalize((0.5,), (0.5,))])
        self._iam = None

    # ---- style references ---------------------------------------------------
    def iam(self):
        if self._iam is None:
            with open(os.path.join(VD, "files", "IAM-32.pickle"), "rb") as f:
                self._iam = pickle.load(f)["test"]
            self.iam_ids = sorted(self._iam.keys())
        return self._iam

    def _word_tensor(self, img):
        img = img.convert("L")
        img = img.resize((max(1, img.width * 32 // img.height), 32), Image.BILINEAR)
        a = np.array(img)
        out = np.full((32, 192), 255, np.uint8)
        w = min(192, a.shape[1])
        out[:, :w] = a[:, :w]
        return self.tf(Image.fromarray(out))

    def _line_chunks(self, img, rng):
        img = img.convert("L")
        img = img.resize((max(1, img.width * 32 // img.height), 32), Image.BILINEAR)
        a = np.array(img)
        chunks = [self._word_tensor(Image.fromarray(a[:, s:s + 192])) for s in range(0, a.shape[1], 192)]
        out = []
        while len(out) < 15:
            out += rng.sample(chunks, len(chunks))
        return out[:15]

    def style_tensor(self, style, refs, seed):
        rng = random.Random(seed)
        if refs:
            imgs = [Image.open(p) for p in refs]
            if len(imgs) == 1:
                ts = self._line_chunks(imgs[0], rng)
                return torch.cat(ts, 0), f"line:{os.path.basename(refs[0])}"
            ts = [self._word_tensor(rng.choice(imgs)) for _ in range(15)]
            return torch.cat(ts, 0), f"words:{len(imgs)}"
        if style is None or isinstance(style, int):
            iam = self.iam()
            idx = style if isinstance(style, int) else rng.randrange(len(self.iam_ids))
            if not 0 <= idx < len(self.iam_ids):
                raise ValueError(f"IAM test writer index must be 0..{len(self.iam_ids) - 1}")
            words = [w for w in iam[self.iam_ids[idx]] if len(w["label"]) >= 2] or iam[self.iam_ids[idx]]
            pick = rng.sample(words, 15) if len(words) >= 15 else [rng.choice(words) for _ in range(15)]
            return torch.cat([self._word_tensor(w["img"]) for w in pick], 0), f"iam_test:{self.iam_ids[idx]}"
        raise ValueError(f"unresolved style {style!r}")

    # ---- generation ---------------------------------------------------------
    @torch.no_grad()
    def generate(self, style_t, text, mode):
        words = [text] if mode == "line" else text.split()
        enc, lens, _ = self.m.netconverter.encode(words)
        st = style_t.unsqueeze(0).repeat(len(words), 1, 1, 1).to(self.device)
        out = self.m.netG.generate(self.m.netG.compute_style(st), enc.to(self.device))
        imgs = [((out[i, 0, :, :int(lens[i]) * 16].float().cpu().numpy() + 1) / 2) for i in range(len(words))]
        if mode == "line":
            return imgs[0]
        try:
            return self.wrapper.stitch_words([im.copy() for im in imgs])
        except Exception:  # noqa: BLE001  baseline detection fails on e.g. "-"
            gap = np.ones((32, 16))
            return np.concatenate(sum([[im, gap] for im in imgs], [])[:-1], axis=1)


def resolve_style(job, refs_db):
    style, p = job.get("style"), job["params"]
    refs = p.get("refs")
    if isinstance(refs, str):
        refs = [refs]
    if refs:
        return None, refs
    if isinstance(style, str):
        if style in refs_db:
            return None, [refs_db[style]["image"]]
        if os.path.isdir(style):
            return None, sorted(os.path.join(style, f) for f in os.listdir(style)
                                if f.lower().endswith((".png", ".jpg", ".jpeg")))
        if os.path.isfile(style):
            return None, [style]
        if style.lstrip("-").isdigit():
            return int(style), None
        raise ValueError(f"style {style!r} is not a known ref name, file or folder")
    return style, None


def load_refs_db(path):
    if not path or not os.path.exists(path):
        return {}
    base = os.path.dirname(os.path.abspath(path))
    db = json.load(open(path, encoding="utf-8"))
    for v in db.values():
        img = v["image"]
        v["image"] = img if os.path.isabs(img) else os.path.join(base, os.path.basename(img))
    return db


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jobs", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--refs-json", default=DEFAULT_REFS)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    jobs = hc.read_jobs(args.jobs)
    refs_db = load_refs_db(args.refs_json)
    t0 = time.time()
    runner = VATrRunner(args.device)
    hc.log(f"VATr++ loaded on {args.device} in {time.time() - t0:.1f}s")
    n_ok = 0
    for k, job in enumerate(jobs):
        t1 = time.time()
        p = {**DEFAULTS, **job["params"]}
        try:
            text = job["text"]
            if not text.strip():
                raise ValueError("empty text")
            allowed = runner.extended if p["allow_unseen"] else runner.trained
            bad = sorted({c for c in text if c not in allowed})
            if bad:
                raise ValueError(f"characters outside the VATr++ alphabet: {bad!r}"
                                 + ("" if p["allow_unseen"] else " (allow_unseen=true to try Unifont glyphs)"))
            unseen = sorted({c for c in text if c not in runner.trained})
            if p["mode"] not in ("words", "line"):
                raise ValueError("mode must be 'words' or 'line'")
            seed = p.get("seed")
            seed = int(seed) if seed is not None else zlib.crc32(job["id"].encode())
            style, refs = resolve_style(job, refs_db)
            st, style_desc = runner.style_tensor(style, refs, seed)
            arr = runner.generate(st, text, p["mode"])
            if args.device == "cuda":
                torch.cuda.synchronize()
            g = (np.clip(arr, 0, 1) * 255).astype(np.uint8)
            native_h = g.shape[0]
            g = hc.crop_ink(g, margin=2, thresh=170)
            up = float(p["upscale"])
            img = Image.fromarray(g, "L")
            if up != 1:
                img = img.resize((round(img.width * up), round(img.height * up)), Image.LANCZOS)
            hc.write_result(args.out, job, GENERATOR, img, time.time() - t1, None,
                            device=args.device, seed=seed, style_used=style_desc,
                            native_height=native_h, unseen_chars=unseen)
            n_ok += 1
        except Exception as e:  # noqa: BLE001
            hc.write_result(args.out, job, GENERATOR, None, time.time() - t1, hc.fmt_exc(e))
            hc.log(f"[{job['id']}] failed: {e}")
        if (k + 1) % 50 == 0:
            hc.log(f"{k + 1}/{len(jobs)}")
    hc.log(f"done: {n_ok}/{len(jobs)} ok in {time.time() - t0:.1f}s -> {args.out}")


if __name__ == "__main__":
    main()
