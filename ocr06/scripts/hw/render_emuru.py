#!/usr/bin/env python
"""Batch renderer for Emuru (blowing-up-groundhogs/emuru, CVPR 2025, MIT), GPU fp32.

    .venv-hw-emuru/bin/python scripts/hw/render_emuru.py --jobs jobs.jsonl --out DIR

Job: {"id": str, "text": str, "style": int | str | null, "params": {...}}
  style   str  = name in --refs-json (reference line image + its transcription)
          int  = index into the sorted names of --refs-json
  params  refs + ref_text   explicit reference: [one line image path] and its exact
                            transcription (overrides style; Emuru needs the text)
          seed              seed of the VAE posterior sample of the reference
                            (default crc32(id)); batching changes results only at float level
          max_tokens_per_char  generation budget, 1 token = 8 px at 64 px height (default 8)
          upscale           output scale from the native 64-px height (default 2)
          allow_unseen      true = accept characters outside printable ASCII (accents...).
                            Off by default: the model often drops them (see report).
          exact_recompute   true = use the original O(n^2) loop (re-runs T5 every step)
                            instead of the KV-cached loop (same maths, ~10x faster)
Output: DIR/<id>.png (grayscale on white, cropped), DIR/<id>.json. A job fails when the
model's end-of-text detector never fires within the budget (usually garbage/truncation).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import zlib

os.environ.setdefault("HF_HUB_OFFLINE", "1")

import numpy as np  # noqa: E402
import torch  # noqa: E402
from PIL import Image  # noqa: E402
from torchvision.transforms import functional as TF  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hwcommon as hc  # noqa: E402

OCR06 = os.path.abspath(os.path.join(HERE, "..", ".."))
DEFAULT_REFS = os.path.join(OCR06, "experiments", "hw_bakeoff", "refs", "refs.json")
GENERATOR = "emuru"
ASCII = {chr(c) for c in range(32, 127)}
DEFAULTS = dict(max_tokens_per_char=8, upscale=2, allow_unseen=False, exact_recompute=False)


def load_style_image(path):
    img = Image.open(path).convert("RGB")
    img = img.resize((max(8, img.width * 64 // img.height), 64), Image.BILINEAR)
    return TF.normalize(TF.to_tensor(img), [0.5], [0.5])


BLANK_PX = 56      # a run of >= 56 blank px (7 latent tokens) after some text = end of line
INK_LEVEL = 0.82   # pixel (0..1) darker than this counts as ink
MIN_TOKENS_PER_CHAR = 2.5  # no end-of-text accepted before this many tokens (20 px) per char


def first_blank_run(cols_ink, start, run=BLANK_PX):
    """Index of the first column >= start that begins a blank run of `run` px, or -1."""
    n = 0
    for x in range(start, len(cols_ink)):
        n = 0 if cols_ink[x] else n + 1
        if n >= run:
            return x - run + 1
    return -1


@torch.inference_mode()
def generate_cached(model, texts, imgs, lengths, max_new_tokens, min_new_tokens=None, seeds=None,
                    stopping_after=10, stopping_patience=1, check_every=4):
    """Emuru._generate with the T5 encoder run once and a decoder KV cache (same maths).

    End of text: the original latent test (cosine similarity to the learned padding token)
    never fired for our references, whose generated background is not the model's blank,
    so a pixel test is added: every few steps the newest 12 tokens are decoded and the
    sample stops once its last 56 px hold no ink. Returns (images, stop_token or -1)."""
    dev = model.device
    tok = model.tokenizer(texts, return_tensors="pt", padding=True)
    input_ids, amask = tok.input_ids.to(dev), tok.attention_mask.to(dev)
    # VAE posterior sample of the reference, with one noise stream per job (seed)
    post = model.vae.encode(imgs.float()).latent_dist
    noise = torch.stack([torch.randn(post.mean.shape[1:], generator=torch.Generator().manual_seed(int(sd)))
                         for sd in (seeds or [0] * imgs.size(0))]).to(dev)
    z_sequence = model.query_rearrange(post.mean + post.std * noise)
    L = torch.tensor(lengths, device=dev)
    L = (L / 8).ceil().int()
    B = z_sequence.size(0)
    total = int(L.max()) + max_new_tokens
    min_new = min_new_tokens or [0] * B
    zmask = torch.zeros((B, total), dtype=torch.bool, device=dev)
    for i, l in enumerate(L):
        zmask[i, :l] = True
    # unlike the original loop, padded text positions are masked, so a job gives the
    # same result alone or in a batch with longer texts
    enc = model.T5.encoder(input_ids=input_ids, attention_mask=amask)
    sos = model.sos.weight.unsqueeze(0).expand(B, 1, -1)
    start = int(L.min())
    canvas = z_sequence[:, :start]
    dec_in = torch.cat([sos, model.vae_to_t5(canvas)], dim=1)
    past = None
    pad = model.padding_token.unsqueeze(0).expand(B, 1, -1)
    stops = torch.full((B,), -1, dtype=torch.long)
    for t in range(start, total):
        out = model.T5(encoder_outputs=enc, attention_mask=amask, decoder_inputs_embeds=dec_in,
                       past_key_values=past, use_cache=True)
        past = out.past_key_values
        pred = model.t5_to_vae(out.logits[:, -1:])[:, 0]
        if t < z_sequence.size(1):
            sl = torch.where(zmask[:, t:t + 1], z_sequence[:, t], pred)
        else:
            sl = pred
        canvas = torch.cat([canvas, sl.unsqueeze(1)], dim=1)
        dec_in = model.vae_to_t5(sl.unsqueeze(1))
        # original latent criterion (kept), searched only after each reference
        sim = torch.nn.functional.cosine_similarity(canvas, pad, dim=-1)
        win = min(stopping_after, sim.size(-1))
        sums = (sim > model.padding_token_threshold).unfold(1, win, 1).int().sum(2)
        for i in range(B):
            if stops[i] >= 0:
                continue
            idx = (sums[i] > (stopping_after - stopping_patience)).nonzero(as_tuple=True)[0]
            idx = idx[idx >= L[i] + min_new[i]]
            if idx.numel():
                stops[i] = int(idx[0])
        # pixel criterion
        if (t - start) % check_every == 0:
            n = canvas.size(1)
            w = min(12, n)
            px = (model.vae.decode(model.z_rearrange(canvas[:, n - w:])).sample.mean(1) + 1) / 2
            tail = px[:, :, -BLANK_PX:]
            blank = (tail > INK_LEVEL).all(dim=2).all(dim=1).cpu()
            for i in range(B):
                if stops[i] < 0 and blank[i] and n - BLANK_PX // 8 >= int(L[i]) + min_new[i]:
                    stops[i] = n - BLANK_PX // 8
        if torch.all(stops >= 0):
            break
    dec = torch.clamp(model.vae.decode(model.z_rearrange(canvas)).sample, -1, 1)
    return dec, stops


@torch.inference_mode()
def generate_exact(model, texts, imgs, lengths, max_new_tokens):
    dec, _, ends = model._generate(texts=texts, imgs=imgs, lengths=lengths, max_new_tokens=max_new_tokens)
    return dec, (ends // 8).long().cpu()


def resolve(job, refs_db, names):
    p, style = job["params"], job.get("style")
    refs = p.get("refs")
    if isinstance(refs, str):
        refs = [refs]
    if refs:
        if len(refs) != 1:
            raise ValueError("Emuru takes exactly one reference line image")
        if not p.get("ref_text"):
            raise ValueError("params.ref_text (transcription of the reference) is required with refs")
        return refs[0], p["ref_text"], f"file:{os.path.basename(refs[0])}"
    if isinstance(style, int) or (isinstance(style, str) and style.isdigit()):
        style = names[int(style)]
    if style is None:
        raise ValueError("Emuru needs a reference: give style (ref name/index) or params.refs + ref_text")
    if style not in refs_db:
        raise ValueError(f"unknown reference {style!r}; known: {names}")
    return refs_db[style]["image"], refs_db[style]["text"], style


def load_refs_db(path):
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
    ap.add_argument("--batch-size", type=int, default=4)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    jobs = hc.read_jobs(args.jobs)
    refs_db = load_refs_db(args.refs_json) if os.path.exists(args.refs_json) else {}
    names = sorted(refs_db)

    t0 = time.time()
    from transformers import AutoModel
    model = AutoModel.from_pretrained("blowing-up-groundhogs/emuru", trust_remote_code=True)
    model.to(args.device).eval()
    hc.log(f"Emuru loaded on {args.device} in {time.time() - t0:.1f}s")

    # validate, then group by reference so a batch shares one style image size
    groups = {}
    for job in jobs:
        p = {**DEFAULTS, **job["params"]}
        try:
            text = job["text"]
            if not text.strip():
                raise ValueError("empty text")
            allowed = None if p["allow_unseen"] else ASCII
            if allowed is not None:
                bad = sorted({c for c in text if c not in allowed})
                if bad:
                    raise ValueError(f"characters outside printable ASCII: {bad!r} "
                                     "(allow_unseen=true to try them anyway)")
            ref_img, ref_text, ref_name = resolve(job, refs_db, names)
            seed = p.get("seed")
            seed = int(seed) if seed is not None else zlib.crc32(job["id"].encode())
            key = (ref_img, ref_text, bool(p["exact_recompute"]))
            groups.setdefault(key, []).append(dict(job=job, p=p, seed=seed, ref_name=ref_name))
        except Exception as e:  # noqa: BLE001
            hc.write_result(args.out, job, GENERATOR, None, 0.0, hc.fmt_exc(e))
            hc.log(f"[{job['id']}] rejected: {e}")

    done = 0
    n_ok = 0
    for (ref_img, ref_text, exact), items in groups.items():
        simg = load_style_image(ref_img)
        items.sort(key=lambda it: len(it["job"]["text"]))
        for b in range(0, len(items), args.batch_size):
            batch = items[b:b + args.batch_size]
            t1 = time.time()
            try:
                torch.manual_seed(batch[0]["seed"])
                texts = [ref_text + " " + it["job"]["text"] for it in batch]
                imgs = simg.unsqueeze(0).repeat(len(batch), 1, 1, 1).to(args.device)
                lengths = [simg.size(-1)] * len(batch)
                budget = max(math.ceil(len(it["job"]["text"]) * float(it["p"]["max_tokens_per_char"]))
                             + 8 for it in batch)
                min_new = [math.ceil(MIN_TOKENS_PER_CHAR * len(it["job"]["text"])) for it in batch]
                if exact:
                    dec, stops = generate_exact(model, texts, imgs, lengths, budget)
                else:
                    dec, stops = generate_cached(model, texts, imgs, lengths, budget, min_new,
                                                 [it["seed"] for it in batch])
                if args.device == "cuda":
                    torch.cuda.synchronize()
                per = (time.time() - t1) / len(batch)
                for i, it in enumerate(batch):
                    try:
                        if int(stops[i]) < 0:
                            raise RuntimeError(f"no end-of-text detected within {budget} tokens "
                                               "(output is truncated or degenerate)")
                        x0, x1 = lengths[i], int(stops[i]) * 8 + BLANK_PX
                        a = ((dec[i, :, :, x0:x1].float().mean(0).cpu().numpy() + 1) / 2)
                        # cut at the first long blank run once some ink was written
                        ink = (a < INK_LEVEL).any(axis=0)
                        first = int(np.argmax(ink)) if ink.any() else len(ink)
                        cut = first_blank_run(ink, max(first, min_new[i] * 8))
                        if cut > 0:
                            a = a[:, :cut]
                        g = (np.clip(a, 0, 1) * 255).astype(np.uint8)
                        if (g < INK_LEVEL * 255).sum() < 20:
                            raise RuntimeError("generated image is blank")
                        g = hc.crop_ink(g, margin=3, thresh=int(INK_LEVEL * 255))
                        img = Image.fromarray(g, "L")
                        up = float(it["p"]["upscale"])
                        if up != 1:
                            img = img.resize((round(img.width * up), round(img.height * up)), Image.LANCZOS)
                        hc.write_result(args.out, it["job"], GENERATOR, img, per, None,
                                        device=args.device, seed=it["seed"], style_used=it["ref_name"],
                                        ref_text=ref_text, native_height=64, batch=len(batch),
                                        tokens_budget=budget, cached=not exact,
                                        unseen_chars=sorted({c for c in it["job"]["text"] if c not in ASCII}))
                        n_ok += 1
                    except Exception as e:  # noqa: BLE001
                        hc.write_result(args.out, it["job"], GENERATOR, None, per, hc.fmt_exc(e),
                                        device=args.device, style_used=it["ref_name"])
                        hc.log(f"[{it['job']['id']}] failed: {e}")
            except Exception as e:  # noqa: BLE001  whole batch failed (e.g. OOM)
                if args.device == "cuda":
                    torch.cuda.empty_cache()
                for it in batch:
                    hc.write_result(args.out, it["job"], GENERATOR, None, time.time() - t1, hc.fmt_exc(e))
                hc.log(f"batch failed: {hc.fmt_exc(e)}")
            done += len(batch)
            hc.log(f"{done}/{sum(len(v) for v in groups.values())} ({time.time() - t0:.0f}s)")
    hc.log(f"done: {n_ok}/{len(jobs)} ok in {time.time() - t0:.1f}s -> {args.out}")


if __name__ == "__main__":
    main()
