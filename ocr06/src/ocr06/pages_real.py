"""Teste de página inteira com manuscrito real em português (nada sintético).

  portexto  121 páginas de cadernos e notas pessoais (pt-PT) digitalizadas, do PorTEXTO
            (subconjunto handwritten_full_page; CC BY-NC 4.0). Gabarito do PorTEXTO:
            Gemini 3.1 Pro, revisado e corrigido por falantes nativos.
            https://huggingface.co/datasets/amalia-llm/PorTEXTO
  bressay   páginas de teste do BRESSAY (redações, pt-BR), de autores fora do treino;
            gabarito humano. As páginas são ampliadas ~3x (a ampliação que as linhas do
            BRESSAY recebem no treino, 20 -> 64 px), com no máximo 2048 px no lado maior.

    python -m ocr06.pages_real bressay   # gera data/pages/bressay/ a partir do zip baixado
    python -m ocr06.pages_real score     # pontua experiments/paginas/<modelo>/{portexto,bressay}.jsonl

O PorTEXTO é extraído uma vez (scripts à parte, precisa de pyarrow) para data/pages/portexto/.
Métrica: CER e WER do texto da página inteira. Antes de comparar, o gabarito e a saída são
normalizados: HTML removido, espaços e quebras de linha unificados e palavras hifenizadas
no fim da linha juntadas ("cinemato- gráfica" -> "cinematográfica"), porque o prompt do
Chandra junta as linhas em parágrafos. No BRESSAY, as marcações da transcrição saem do
gabarito: trecho ilegível (@@???@@) e riscado (--...--) são removidos, e texto sobrescrito
ou subscrito (##...##, $$...$$) fica no lugar. Como a ordem de leitura de anotações à
margem pode variar, o CER é uma medida aproximada; o que importa é a comparação base x treinado
nas mesmas páginas.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import zipfile

import numpy as np

from .common import load_config, resolve
from .evaluate import normalize

SETS = ("portexto", "bressay")
HYPHEN = re.compile(r"(\w)- (\w)")


def clean_bressay(t: str) -> str:
    t = re.sub(r"##--.*?--##|\$\$--.*?--\$\$", " ", t)    # sobrescrito/subscrito riscado
    t = re.sub(r"--.*?--", " ", t)                          # riscado (legível ou não)
    t = re.sub(r"(##|\$\$)@@\?\?\?@@(##|\$\$)|@@\?\?\?@@", " ", t)  # ilegível
    return re.sub(r"##(.*?)##|\$\$(.*?)\$\$", lambda m: m.group(1) or m.group(2) or "", t)


def page_text(t: str) -> str:
    t = normalize(t)  # tira HTML, desfaz entidades, NFC, espaços
    t = t.replace("$", "")  # LaTeX inline do gabarito ($E_1$) x <math> da saída
    return HYPHEN.sub(r"\1\2", t)


def edit_distance(a, b) -> int:
    """Levenshtein vetorizado por linha (strings longas de página inteira)."""
    if len(a) < len(b):
        a, b = b, a
    if not b:
        return len(a)
    if isinstance(a, str):
        A = np.frombuffer(a.encode("utf-32-le"), dtype=np.uint32)
        B = np.frombuffer(b.encode("utf-32-le"), dtype=np.uint32)
    else:  # listas de palavras
        vocab = {w: i for i, w in enumerate(set(a) | set(b))}
        A = np.array([vocab[w] for w in a])
        B = np.array([vocab[w] for w in b])
    ar = np.arange(len(B) + 1, dtype=np.int64)
    prev = ar.copy()
    for i, x in enumerate(A, 1):
        best = np.minimum(prev[:-1] + (B != x), prev[1:] + 1)
        tmp = np.concatenate([[i], best])
        prev = np.minimum.accumulate(tmp - ar) + ar
    return int(prev[-1])


def build_bressay(cfg: dict) -> None:
    from PIL import Image
    raw = resolve(cfg, "raw") / "bressay"
    zpath = next(raw.rglob("bressay.zip"))
    out = resolve(cfg, "raw").parent / "pages" / "bressay"
    (out / "images").mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zpath) as z:
        names = set(z.namelist())
        test = z.read("bressay/sets/test.txt").decode("utf-8").split()
        rows = []
        for pid in test:
            png, txt = f"bressay/data/pages/{pid}/{pid}.png", f"bressay/data/pages/{pid}/{pid}.txt"
            if png not in names or txt not in names:
                continue
            with z.open(png) as f:
                im = Image.open(f).convert("RGB")
            # ~3x (como as linhas no treino), mas no máximo 2048 px no lado maior: há
            # páginas bem maiores que as outras e passariam do limite de tokens do modelo.
            s = min(3.0, 2048 / max(im.size))
            im = im.resize((round(im.width * s), round(im.height * s)), Image.Resampling.BICUBIC)
            im.save(out / "images" / f"{pid}.jpg", quality=92)
            rows.append({"id": f"bressay_{pid}", "image": f"pages/bressay/images/{pid}.jpg",
                         "text": z.read(txt).decode("utf-8")})
    with open(out / "pages.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  bressay: {len(rows)} páginas de teste -> {out}")


def score(cfg: dict) -> dict:
    data = resolve(cfg, "raw").parent / "pages"
    root = resolve(cfg, "experiments") / "paginas"
    results: dict = {}
    for name in SETS:
        gold_path = data / name / "pages.jsonl"
        if not gold_path.exists():
            continue
        gold = {r["id"]: r["text"] for r in map(json.loads, open(gold_path, encoding="utf-8"))}
        for f in sorted(root.glob(f"*/{name}.jsonl")):
            dc = nc = dw = nw = 0
            per_page = {}
            for r in map(json.loads, open(f, encoding="utf-8")):
                g = gold[r["id"]]
                # gabarito é texto puro: escapa "<" e ">" para não virarem "tag" na normalização
                g = page_text(html.escape(clean_bressay(g) if name == "bressay" else g, quote=False))
                p = page_text(r["pred"])
                d = edit_distance(g, p)
                dc, nc = dc + d, nc + len(g)
                gw, pw = g.split(), p.split()
                dw, nw = dw + edit_distance(gw, pw), nw + len(gw)
                per_page[r["id"]] = d / max(len(g), 1)
            results.setdefault(name, {})[f.parent.name] = {
                "paginas": len(per_page), "cer": dc / max(nc, 1), "wer": dw / max(nw, 1),
                "por_pagina": per_page}
    lines = ["Páginas inteiras com manuscrito real (CER/WER do texto da página, em %).", "",
             "| Conjunto | Modelo | Páginas | CER | WER | Páginas melhores que a base |",
             "|---|---|---|---|---|---|"]
    for name, models in results.items():
        base = models.get("base", {}).get("por_pagina", {})
        for tag, m in models.items():
            better = "-" if tag == "base" or not base else \
                f"{sum(m['por_pagina'][k] < base[k] for k in m['por_pagina'] if k in base)}/{len(base)}"
            lines.append(f"| {name} | {tag} | {m['paginas']} | {100 * m['cer']:.1f} | "
                         f"{100 * m['wer']:.1f} | {better} |")
    (root / "comparacao_real.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (root / "comparacao_real.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    print("\n".join(lines))
    return results


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["bressay", "score"])
    ap.add_argument("--config", default="configs/default.yaml")
    args = ap.parse_args()
    cfg = load_config(args.config)
    build_bressay(cfg) if args.cmd == "bressay" else score(cfg)


if __name__ == "__main__":
    main()
