"""Geração do dataset sintético: amostra texto -> renderiza -> degrada -> controle de qualidade.

Saída em data/synthetic/<nome>/:
  <split>/images/<split>_0000000.jpg
  <split>/labels.jsonl   (texto exato + spans das entidades com bucket comum/raro/inventado)
  vocab.json             (vocabulário selecionado e nomes reservados para val/test)
  manifest.json          (config usada, contagens, rejeições, tempo, versões)
Cada amostra i tem seed derivada de (seed global, split, i): rodar de novo gera a
mesma imagem, independente do número de workers.
"""
from __future__ import annotations

import json
import time
from collections import Counter
from datetime import datetime, timezone
from multiprocessing import Pool
from pathlib import Path

import os

import cv2
import numpy as np
from tqdm import tqdm

from .common import read_json, resolve, stable_int, write_json
from .degrade import Degrader, ink_contrast
from .fonts import fonts_for_split
from .render import render_line
from .sampler import NameSampler
from .vocab import select_vocab

_W: dict = {}


def n_workers(cfg: dict) -> int:
    w = cfg["generate"]["workers"]
    return (os.cpu_count() or 1) if w in (None, "auto", 0) else int(w)


def _init_worker(cfg: dict, split: str, out_dir: str, vocab_path: str) -> None:
    cv2.setNumThreads(1)
    _W.update(
        cfg=cfg, split=split, out=Path(out_dir),
        sampler=NameSampler(resolve(cfg, "lexicon"), split, cfg["sampling"],
                            read_json(Path(vocab_path))),
        fonts=fonts_for_split(cfg, split),
        degrader=Degrader(cfg["degrade"]),
    )


def make_sample(cfg: dict, split: str, i: int, sampler, fonts, degrader):
    """Gera a amostra i; tenta outra seed se a degradação apagar demais a tinta."""
    dc = cfg["degrade"]
    rejected = 0
    for attempt in range(dc["max_retries"] + 1):
        seed = stable_int(cfg["seed"], split, i, attempt)
        rng = np.random.default_rng(seed)
        sample = sampler.compose(rng, cfg["sampling"]["templates"])
        font = fonts[rng.integers(len(fonts))]
        bgr, mask, rinfo = render_line(sample["text"], font, cfg["render"], rng)
        img, level = degrader(bgr, seed, rng)
        contrast = ink_contrast(img, mask)
        if contrast >= dc["min_contrast"]:
            break
        rejected += 1
    sample.update(font=Path(font).stem, degrade=level, contrast=round(contrast, 1),
                  seed=seed, width=img.shape[1], height=img.shape[0], **rinfo)
    return sample, img, rejected


def _work(i: int):
    w = _W
    sample, img, rejected = make_sample(w["cfg"], w["split"], i,
                                        w["sampler"], w["fonts"], w["degrader"])
    name = f"{w['split']}_{i:07d}.jpg"
    cv2.imwrite(str(w["out"] / "images" / name), img,
                [cv2.IMWRITE_JPEG_QUALITY, w["cfg"]["degrade"]["jpeg_quality"]])
    sample = {"id": f"{w['split']}_{i:07d}", "image": f"images/{name}", **sample}
    return i, sample, rejected


def generate_split(cfg: dict, split: str, n: int, out_dir: Path, workers: int,
                   vocab_path: Path) -> dict:
    (out_dir / "images").mkdir(parents=True, exist_ok=True)
    results: dict[int, dict] = {}
    rejected = 0
    t0 = time.time()
    with Pool(workers, initializer=_init_worker,
              initargs=(cfg, split, str(out_dir), str(vocab_path))) as pool:
        for i, sample, rej in tqdm(pool.imap_unordered(_work, range(n), chunksize=16),
                                   total=n, desc=split):
            results[i] = sample
            rejected += rej
    elapsed = time.time() - t0
    with open(out_dir / "labels.jsonl", "w", encoding="utf-8") as f:
        for i in range(n):
            f.write(json.dumps(results[i], ensure_ascii=False) + "\n")
    buckets = Counter(e["bucket"] for s in results.values() for e in s["entities"]
                      if e["bucket"])
    size = sum(p.stat().st_size for p in (out_dir / "images").iterdir())
    return {
        "n": n, "segundos": round(elapsed, 1), "imagens_por_segundo": round(n / elapsed, 2),
        "rejeicoes_contraste": rejected, "bytes": size,
        "templates": dict(Counter(s["template"] for s in results.values())),
        "niveis_degradacao": dict(Counter(s["degrade"] for s in results.values())),
        "tokens_por_bucket": dict(buckets),
    }


def generate(cfg: dict, name: str, splits: list[str], n: int | None = None) -> Path:
    root = resolve(cfg, "synthetic") / name
    root.mkdir(parents=True, exist_ok=True)
    workers = n_workers(cfg)
    vocab_path = root / "vocab.json"
    if "train" in splits or not vocab_path.exists():
        # O vocabulário depende do tamanho do treino; splits gerados depois reusam o mesmo.
        n_train = n if (n is not None and "train" in splits) else cfg["generate"]["n"]["train"]
        vocab = select_vocab(cfg, resolve(cfg, "lexicon"), n_train)
        write_json(vocab_path, vocab)
        for k in ("prenome", "sobrenome", "cidade"):
            v = vocab[k]
            print(f"  vocab {k}: K={v['K']} cobertura={v['cobertura_populacao']:.3f} "
                  f"min_esperado={v['min_esperado_treino']:.1f} splits={v['por_split']}")
            if v["por_split"]["test"] == 0:
                print(f"  AVISO: nada do tipo '{k}' reservado para o teste (orçamento pequeno "
                      f"demais: o vocabulário só tem nomes comuns), então não haverá '{k}' "
                      f"inédito no teste por construção.")
    stats = {}
    for split in splits:
        count = n if n is not None else cfg["generate"]["n"][split]
        stats[split] = generate_split(cfg, split, count, root / split, workers, vocab_path)
        print(f"  {split}: {stats[split]}")
    import augraphy
    write_json(root / "manifest.json", {
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "config": cfg,
        "lexicon_meta": json.loads((resolve(cfg, "lexicon") / "meta.json").read_text()),
        "versoes": {"augraphy": getattr(augraphy, "__version__", "?"), "opencv": cv2.__version__,
                    "numpy": np.__version__},
        "splits": stats,
    })
    return root
