"""Side-by-side readings of each handwritten field, per model, to look at the misses.

    python scripts/erros_paginas.py --set teste_local --models base_g4 lora_v1 lora_v2 lora_v2_fp8 lora_v2_int4

For every field (same rules as pages_eval: no accent-stripped, short fields apart) it takes, in
each model's output, the stretch closest to the gold value inside the blocks whose box touches the
field ("local" reading). Writes experiments/paginas/erros_<set>.md (fields any model got wrong,
grouped by class) and erros_<set>.jsonl (every field)."""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ocr06.pages_eval import MARGIN, compact, fields_of, infix_span, overlaps, page_size, parse_blocks  # noqa: E402


def reading(f, blocks, full) -> tuple[str, int]:
    if f.box is not None:
        hay = " ".join(b.text for b in blocks if overlaps(b.bbox, f.box, MARGIN))
    else:
        hay = full
    if f.cls == "number":
        hay = compact(hay)
    d, s, e = infix_span(f.cmp, hay)
    return hay[s:e], d


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="teste_local")
    ap.add_argument("--models", nargs="+", required=True)
    a = ap.parse_args()
    data = ROOT / "data"
    out_dir = ROOT / "experiments" / "paginas"
    gold = [json.loads(l) for l in open(data / "pages" / a.set / "pages.jsonl", encoding="utf-8")]
    preds = {m: {r["id"]: r for r in map(json.loads, open(out_dir / m / f"{a.set}.jsonl", encoding="utf-8"))}
             for m in a.models}
    rows = []
    for g in gold:
        if not all(g["id"] in preds[m] for m in a.models):
            continue
        fields = [f for f in fields_of(g, page_size(g, data)) if not f.stripped and not f.short]
        parsed = {}
        for m in a.models:
            text = preds[m][g["id"]].get("pred") or ""
            from ocr06.evaluate import normalize
            parsed[m] = (parse_blocks(text), normalize(text))
        for f in fields:
            r = {"id": g["id"], "template": g.get("template"), "label": f.label, "cls": f.cls, "gold": f.cmp}
            for m in a.models:
                txt, d = reading(f, *parsed[m])
                r[m] = txt
                r[m + "_ok"] = d == 0
            rows.append(r)
    with open(out_dir / f"erros_{a.set}.jsonl", "w", encoding="utf-8") as fo:
        for r in rows:
            fo.write(json.dumps(r, ensure_ascii=False) + "\n")

    def cell(r, m):
        t = r[m].replace("|", "/") or "∅"
        return t if r[m + "_ok"] else f"**{t}**"

    L = [f"# Leituras por campo: {a.set}", "",
         f"{len(rows)} campos manuscritos (sem os curtos e os sem acento), {len({r['id'] for r in rows})} páginas. "
         "Leitura local: trecho da saída mais parecido com o gabarito, nos blocos que encostam na caixa do campo. "
         "Em **negrito**: errado (≠ gabarito).", ""]
    ok = {m: sum(r[m + "_ok"] for r in rows) for m in a.models}
    L += ["| Modelo | Certos | % |", "|---|---|---|"]
    L += [f"| {m} | {ok[m]} | {100 * ok[m] / len(rows):.1f} |" for m in a.models]
    first, last = a.models[0], a.models[1] if len(a.models) > 1 else a.models[0]
    for m in a.models[1:]:
        fix = sum(r[m + "_ok"] and not r[first + "_ok"] for r in rows)
        brk = sum(r[first + "_ok"] and not r[m + "_ok"] for r in rows)
        L.append(f"\n{m} contra {first}: conserta {fix}, estraga {brk}.")
    for cls in sorted({r["cls"] for r in rows}):
        bad = [r for r in rows if r["cls"] == cls and not all(r[m + "_ok"] for m in a.models)]
        L += ["", f"## {cls}: {len(bad)} campos com algum erro", "",
              "| Página | Campo | Gabarito | " + " | ".join(a.models) + " |",
              "|---|---|---|" + "---|" * len(a.models)]
        for r in bad:
            L.append(f"| {r['id']} | {r['label']} | {r['gold']} | " + " | ".join(cell(r, m) for m in a.models) + " |")
    (out_dir / f"erros_{a.set}.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L[:12 + len(a.models)]))
    print(f"-> {out_dir / f'erros_{a.set}.md'}")


if __name__ == "__main__":
    main()
