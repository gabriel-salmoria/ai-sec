"""Que tipo de erro o lora_v2 ainda comete nos nomes, e quão perto do certo o Chandra estava
nos campos que o lora_v2 corrigiu.

    python3 scripts/erros_restantes.py

Prenome aqui é só a primeira palavra do campo, então o segundo prenome de um nome composto
conta como "erro depois do prenome". Comum e raro seguem o bucket do léxico (prenomes.csv).
Lê experiments/paginas/erros_<set>.jsonl e avaliacao_<set>.json; grava
experiments/paginas/erros_restantes.md."""
import csv
import json
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "experiments" / "paginas"


def chave(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).upper()


bucket = {r["key"]: r["bucket"] for r in csv.DictReader(open(ROOT / "data" / "lexicon" / "prenomes.csv", encoding="utf-8"))}
GRUPOS = ["prenome certo, erro depois dele", "prenome lido como algo fora do léxico",
          "prenome raro lido como outro prenome raro", "prenome raro lido como prenome comum",
          "prenome comum lido como outro prenome", "leitura vazia"]

L = ["# Erros restantes do lora_v2 nos nomes", ""]
for s in ("teste_local", "forms_v2_normal"):
    c = Counter()
    for r in map(json.loads, open(P / f"erros_{s}.jsonl", encoding="utf-8")):
        if r["cls"] != "name" or r["lora_v2_ok"]:
            continue
        g, p = r["gold"].split(), r["lora_v2"].split()
        if not p:
            c["leitura vazia"] += 1
        elif chave(p[0]) == chave(g[0]):
            c["prenome certo, erro depois dele"] += 1
        elif chave(p[0]) not in bucket:
            c["prenome lido como algo fora do léxico"] += 1
        elif bucket.get(chave(g[0])) == "comum":
            c["prenome comum lido como outro prenome"] += 1
        elif bucket[chave(p[0])] == "comum":
            c["prenome raro lido como prenome comum"] += 1
        else:
            c["prenome raro lido como outro prenome raro"] += 1
    total = sum(c.values())
    L += [f"## {s}: {total} campos de nome errados", "", "| Tipo | Campos | % |", "|---|---|---|"]
    L += [f"| {g} | {c[g]} | {100 * c[g] / total:.0f} |" for g in GRUPOS]

    campos = json.load(open(P / f"avaliacao_{s}.json", encoding="utf-8"))["por_campo"]
    d = Counter()
    for a, b in zip(campos["base_g4"], campos["lora_v2"]):
        if not a["short"] and not a["exato_local"] and b["exato_local"]:
            d[min(a["d_local"], 3)] += 1
    n = sum(d.values())
    L += ["", f"Campos que o Chandra errava e o lora_v2 acerta: {n}. Distância de edição da leitura do Chandra: "
          f"1 caractere em {d[1]} ({100 * d[1] / n:.0f}%), 2 em {d[2]} ({100 * d[2] / n:.0f}%), 3 ou mais em {d[3]}.", ""]
(P / "erros_restantes.md").write_text("\n".join(L), encoding="utf-8")
print("\n".join(L))
