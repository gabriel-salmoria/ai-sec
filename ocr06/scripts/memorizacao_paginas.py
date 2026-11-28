"""Acerto exato dos campos de nome, separado entre campos com todas as palavras vistas em alguma
página de treino e campos com pelo menos uma palavra nunca vista. Se o ganho viesse de decorar
os nomes do treino, ele apareceria nos vistos e não nos inéditos.

    .venv/bin/python scripts/memorizacao_paginas.py

Lê experiments/paginas/erros_<set>.jsonl (gerado por scripts/erros_paginas.py) e as páginas que
entraram no treino do lora_v1 e do lora_v2 (data/final/pages_v1 e pages_v2, train.jsonl). Grava
experiments/paginas/memorizacao_nomes.md."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ocr06.evaluate import normalize  # noqa: E402

DATA, OUT = ROOT / "data" / "pages", ROOT / "experiments" / "paginas"
treino = {json.loads(l)["id"] for v in ("pages_v1", "pages_v2")
          for l in open(ROOT / "data" / "final" / v / "train.jsonl", encoding="utf-8")}
seen, n_pages = set(), 0
for name in ("forms_v1", "forms_v2", "ocrsd"):
    for line in open(DATA / name / "pages.jsonl", encoding="utf-8"):
        row = json.loads(line)
        if row["id"] not in treino:
            continue
        n_pages += 1
        for f in row["fields"]:
            seen.update(normalize(f.get("text") or f.get("value") or "").split())

L = ["# Nomes vistos e inéditos nas páginas de teste", "",
     f"Palavras vistas: as que aparecem em algum campo de {n_pages} páginas de treino ({len(seen)} palavras). "
     "Acerto exato local dos campos de nome, em %.", ""]
for s in ("teste_local", "forms_v2_normal"):
    rows = [json.loads(l) for l in open(OUT / f"erros_{s}.jsonl", encoding="utf-8")]
    models = [k[:-3] for k in rows[0] if k.endswith("_ok")]
    names = [r for r in rows if r["cls"] == "name"]
    groups = {"todas as palavras vistas": [], "alguma palavra inédita": []}
    for r in names:
        key = "todas as palavras vistas" if all(w in seen for w in r["gold"].split()) else "alguma palavra inédita"
        groups[key].append(r)
    L += [f"## {s}", "", "| Grupo | Campos | " + " | ".join(models) + " |", "|---|---|" + "---|" * len(models)]
    for g, rs in groups.items():
        L.append(f"| {g} | {len(rs)} | " + " | ".join(
            f"{100 * sum(r[m + '_ok'] for r in rs) / max(1, len(rs)):.1f}" for m in models) + " |")
    L.append("")
(OUT / "memorizacao_nomes.md").write_text("\n".join(L), encoding="utf-8")
print("\n".join(L))
