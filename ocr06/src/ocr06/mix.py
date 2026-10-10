"""Mistura final: sintético + BRESSAY no formato de conversa do VLM.

Saída em data/final/<nome>/:
  train.jsonl, val.jsonl            sintético + BRESSAY embaralhados
  test_sintetico.jsonl              teste sintético (nomes reservados nunca vistos)
  test_bressay.jsonl                teste real (autores fora do treino)
  manifest.json                     contagens, fração real, nomes inéditos no teste
Cada linha: {id, source, image (relativo a data/), messages, text, entities}, e no
teste cada entidade tem `visto_no_treino`, para medir o CER só em nomes inéditos.

Regra da POC: o treino deve ser majoritariamente sintético. Se o BRESSAY passar de
`max_real_fraction`, ele é subamostrado (com seed fixa).
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from .common import resolve, write_json

PROMPT = ("Transcreva exatamente o texto manuscrito desta imagem, preservando a grafia, "
          "os acentos e as maiúsculas. Não corrija nomes.")
NAME_TYPES = ("prenome", "sobrenome", "cidade")


def _load(path: Path, prefix: str) -> list[dict]:
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            s = json.loads(line)
            s["image"] = f"{prefix}/{s['image']}" if prefix else s["image"]
            s.setdefault("source", "sintetico")
            out.append(s)
    return out


def _chat(s: dict) -> dict:
    return {
        "id": s["id"], "source": s["source"], "image": s["image"], "text": s["text"],
        "entities": s.get("entities", []),
        "messages": [
            {"role": "user", "content": [{"type": "image"}, {"type": "text", "text": PROMPT}]},
            {"role": "assistant", "content": [{"type": "text", "text": s["text"]}]},
        ],
    }


def _write(path: Path, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def build(cfg: dict, name: str) -> dict:
    data_dir = resolve(cfg, "raw").parent
    syn_root = resolve(cfg, "synthetic") / name
    bre_root = resolve(cfg, "bressay")
    out = resolve(cfg, "final") / name
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(cfg["seed"])

    def syn(split):
        p = syn_root / split / "labels.jsonl"
        if not p.exists():
            raise FileNotFoundError(f"{p} não existe; rode `generate` antes")
        return _load(p, str((syn_root / split).relative_to(data_dir)))

    def bre(split):
        p = bre_root / split / "labels.jsonl"
        if not p.exists():
            raise FileNotFoundError(f"{p} não existe; rode `bressay` antes")
        return _load(p, "")

    syn_train, bre_train = syn("train"), bre("train")
    max_frac = cfg["mix"]["max_real_fraction"]
    max_real = int(max_frac / (1 - max_frac) * len(syn_train))
    subsampled = len(bre_train) > max_real
    if subsampled:
        bre_train = rng.sample(bre_train, max_real)
    train = syn_train + bre_train
    real_frac = len(bre_train) / len(train)
    assert real_frac <= max_frac + 1e-9, "treino ficou majoritariamente real"
    rng.shuffle(train)
    val = syn("val") + bre("val")
    rng.shuffle(val)

    seen = {(e["type"], e["key"]) for s in train for e in s.get("entities", [])
            if e["type"] in NAME_TYPES}
    seen_keys = {k for t, k in seen if t != "cidade"}  # PEDRO prenome == PEDRO sobrenome
    tests = {"test_sintetico": syn("test"), "test_bressay": bre("test")}
    test_stats = {}
    for tname, rows in tests.items():
        n_ent = n_new = lines_new = 0
        for s in rows:
            has_new = False
            for e in s.get("entities", []):
                if e["type"] not in NAME_TYPES:
                    continue
                v = ((e["type"], e["key"]) in seen if e["type"] == "cidade"
                     else e["key"] in seen_keys)
                e["visto_no_treino"] = v
                n_ent += 1
                n_new += not v
                has_new |= not v
            lines_new += has_new
        test_stats[tname] = {"linhas": len(rows), "entidades_nome": n_ent,
                             "entidades_ineditas": n_new, "linhas_com_nome_inedito": lines_new}
        _write(out / f"{tname}.jsonl", [_chat(s) for s in rows])

    _write(out / "train.jsonl", [_chat(s) for s in train])
    _write(out / "val.jsonl", [_chat(s) for s in val])
    manifest = {
        "dataset_sintetico": name,
        "caminhos_de_imagem_relativos_a": str(data_dir),
        "treino": {"total": len(train), "sintetico": len(syn_train), "bressay": len(bre_train),
                   "fracao_real": round(real_frac, 4), "bressay_subamostrado": subsampled},
        "val": {"total": len(val)},
        "teste": test_stats,
    }
    write_json(out / "manifest.json", manifest)
    print(f"  treino: {manifest['treino']}")
    for t, st in test_stats.items():
        print(f"  {t}: {st}")
    return manifest
