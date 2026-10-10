"""Avaliação: CER/WER das transcrições do modelo contra o gabarito (Python puro).

    python -m ocr06.evaluate      # avalia tudo em experiments/modelos/<modelo>/<prompt>/<split>.jsonl

Métricas (as da seção 3.2 do relatório), por arquivo de predições:
  - CER e WER da linha inteira (micro: soma das distâncias / soma dos tamanhos);
  - CER e acerto exato por entidade, separados por tipo (prenome/sobrenome/cidade),
    por bucket (comum/raro/inventado) e por `visto_no_treino` (inédito vs visto).
Para medir a entidade, a predição é alinhada ao gabarito (Levenshtein com backtrace)
e o trecho da predição alinhado ao span da entidade é comparado com ela.
A predição passa por uma normalização leve: remove HTML (o prompt nativo do Chandra
responde em HTML), desfaz entidades HTML, NFC e espaços repetidos.
Saída: <split>.metricas.json ao lado das predições e experiments/modelos/comparacao.{md,tex,json}.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

from .common import load_config, resolve

TAG = re.compile(r"<[^>]+>")
NAME_TYPES = ("prenome", "sobrenome", "cidade")


def normalize(s: str) -> str:
    s = TAG.sub(" ", s)
    s = html.unescape(s)
    s = s.replace("```", " ")
    s = unicodedata.normalize("NFC", s)
    return " ".join(s.split())


def distance(a, b) -> int:
    """Distância de Levenshtein entre sequências (strings ou listas de palavras)."""
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def align(gold: str, pred: str) -> list[int]:
    """Para cada posição 0..len(gold) do gabarito, a posição correspondente na predição."""
    n, m = len(gold), len(pred)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        gi = gold[i - 1]
        row, prow = d[i], d[i - 1]
        for j in range(1, m + 1):
            row[j] = min(prow[j] + 1, row[j - 1] + 1, prow[j - 1] + (gi != pred[j - 1]))
    pos = [0] * (n + 1)
    i, j = n, m
    pos[n] = m
    while i > 0:
        if j > 0 and d[i][j] == d[i - 1][j - 1] + (gold[i - 1] != pred[j - 1]):
            i, j = i - 1, j - 1
        elif d[i][j] == d[i - 1][j] + 1:
            i -= 1
        else:
            j -= 1
            continue
        pos[i] = j
    return pos


class Acc:
    def __init__(self):
        self.err = self.tot = self.exact = self.n = 0

    def add(self, gold: str, pred: str, unit: str = "char") -> None:
        g, p = (gold, pred) if unit == "char" else (gold.split(), pred.split())
        self.err += distance(g, p)
        self.tot += len(g)
        self.exact += gold == pred
        self.n += 1

    def out(self) -> dict:
        return {"n": self.n, "taxa_erro": round(self.err / self.tot, 4) if self.tot else None,
                "acerto_exato": round(self.exact / self.n, 4) if self.n else None}


def evaluate_file(path: Path) -> dict:
    rows = [json.loads(line) for line in open(path, encoding="utf-8")]
    cer, wer = Acc(), Acc()
    by_source = defaultdict(Acc)
    ent = defaultdict(Acc)
    for r in rows:
        gold, pred = r["text"], normalize(r["pred"])
        cer.add(gold, pred)
        wer.add(gold, pred, "word")
        by_source[r["source"]].add(gold, pred)
        ents = [e for e in r.get("entities", []) if e["type"] in NAME_TYPES]
        if not ents:
            continue
        pos = align(gold, pred)
        for e in ents:
            g, p = gold[e["start"]:e["end"]], pred[pos[e["start"]]:pos[e["end"]]].strip()
            seen = e.get("visto_no_treino")
            groups = ["todas", f"tipo/{e['type']}", f"bucket/{e['bucket']}"]
            if seen is not None:
                groups.append("ineditas" if not seen else "vistas")
                groups.append(f"{'ineditas' if not seen else 'vistas'}/{e['type']}")
            for gname in groups:
                ent[gname].add(g, p)
    return {
        "arquivo": str(path),
        "linhas": len(rows),
        "cer": cer.out()["taxa_erro"], "wer": wer.out()["taxa_erro"],
        "linhas_exatas": cer.out()["acerto_exato"],
        "cer_por_fonte": {k: v.out()["taxa_erro"] for k, v in by_source.items()},
        "entidades": {k: v.out() for k, v in sorted(ent.items())},
    }


def _fmt(x) -> str:
    return "-" if x is None else f"{100 * x:.1f}".replace(".", ",")


def comparison(results: list[dict], out_dir: Path) -> None:
    cols = [("CER", lambda r: r["cer"]), ("WER", lambda r: r["wer"]),
            ("CER nomes", lambda r: r["entidades"].get("todas", {}).get("taxa_erro")),
            ("CER raros", lambda r: r["entidades"].get("bucket/raro", {}).get("taxa_erro")),
            ("CER inéditos", lambda r: r["entidades"].get("ineditas", {}).get("taxa_erro")),
            ("Nomes exatos", lambda r: r["entidades"].get("todas", {}).get("acerto_exato"))]
    head = ["Modelo", "Prompt", "Teste"] + [c for c, _ in cols]
    md = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    tex = [r"\begin{tabular}{@{}lll" + "r" * len(cols) + "@{}}", r"\toprule",
           " & ".join(head).replace("%", r"\%") + r" \\", r"\midrule"]
    for r in sorted(results, key=lambda r: (r["teste"], r["modelo"], r["prompt"])):
        vals = [r["modelo"], r["prompt"], r["teste"]] + [_fmt(f(r)) for _, f in cols]
        md.append("| " + " | ".join(vals) + " |")
        tex.append(" & ".join(v.replace("_", r"\_") for v in vals) + r" \\")
    tex += [r"\bottomrule", r"\end{tabular}"]
    (out_dir / "comparacao.md").write_text("Valores em %.\n\n" + "\n".join(md) + "\n", encoding="utf-8")
    (out_dir / "comparacao.tex").write_text("\n".join(tex) + "\n", encoding="utf-8")
    (out_dir / "comparacao.json").write_text(json.dumps(results, indent=2, ensure_ascii=False),
                                             encoding="utf-8")
    print("\n".join(md))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--dir", help="pasta de predições (padrão: experiments/modelos)")
    args = ap.parse_args()
    cfg = load_config(args.config)
    root = Path(args.dir) if args.dir else resolve(cfg, "experiments") / "modelos"
    files = sorted(p for p in root.glob("*/*/*.jsonl"))
    if not files:
        raise SystemExit(f"nenhuma predição em {root}/<modelo>/<prompt>/<split>.jsonl")
    results = []
    for p in files:
        m = evaluate_file(p)
        m.update(modelo=p.parent.parent.name, prompt=p.parent.name, teste=p.stem)
        p.with_suffix(".metricas.json").write_text(json.dumps(m, indent=2, ensure_ascii=False),
                                                    encoding="utf-8")
        results.append(m)
    comparison(results, root)


if __name__ == "__main__":
    main()
