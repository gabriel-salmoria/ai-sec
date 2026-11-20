"""Pontuação de páginas inteiras de formulários: dois ou mais modelos nas mesmas páginas.

    python -m ocr06.pages_eval --set ocrsd --models base ft

Lê o gabarito em data/pages/<set>/pages.jsonl (campos manuscritos com `text`, `cls`,
`box` em pixels da imagem ou `bbox_1000`, `accent_stripped`) e as predições em
experiments/paginas/<modelo>/<set>.jsonl ({id, pred, tokens, fim}, saída nativa do
Chandra em blocos `<div data-bbox data-label>`). Grava experiments/paginas/avaliacao_<set>.{md,json}.

Campos manuscritos (os com `accent_stripped` ficam de fora: a tinta não tem o acento do
gabarito). Cada campo é procurado de dois jeitos:
  livre  distância de edição até o trecho mais parecido da saída inteira (alinhamento
         infixo, o critério de pages.py). Tolera ordem de leitura diferente, mas um nome
         lido errado no campo dele ainda casa se aparece certo em outro campo (filiação).
  local  o mesmo, só no texto dos blocos cuja caixa encosta na caixa do campo (convertida
         para 0-1000, com margem). Mede se o valor está certo no lugar certo.
Em campos `number` comparam-se só letras e dígitos (o modelo separa os dígitos das
caixinhas: "1 9 8 0"). Campos de até 3 caracteres ("17", "M") casam por acaso em qualquer
página e vão para uma tabela à parte, fora dos totais.

Página: completude (fração dos campos achados com CER <= 0,2), truncamento (`fim ==
"length"` ou os últimos campos na ordem de leitura faltando, com os primeiros presentes e
nenhum bloco na altura deles), laço (trecho que se repete em sequência, ou saída bem mais
longa que a dos outros modelos na mesma página) e mudança no texto impresso em relação ao
modelo de referência (CER entre as duas saídas depois de apagar os valores manuscritos).

Comparação pareada com a referência (padrão `base`): diferença de acerto exato dos campos
(todos e nomes) e de completude, com IC de 95% por bootstrap pareado sobre páginas, e
teste de McNemar (exato) nos acertos campo a campo. Recortes por template, nível, escrita
e split quando o gabarito tem esses campos.
"""
from __future__ import annotations

import argparse
import html
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .common import load_config, resolve
from .evaluate import normalize
from .pages import infix_distance
from .pages_real import edit_distance

FOUND_CER = 0.2        # campo "achado" na página (completude, truncamento)
SHORT = 3              # campos com até 3 caracteres ficam fora dos totais
MARGIN = 20            # folga (escala 0-1000) ao cruzar caixa do campo com caixa do bloco
ERASE_CER = 0.35       # apagar um valor manuscrito da saída só se casar com CER <= isso
LOOP_MIN_RUN = 100     # caracteres repetidos em sequência para contar como laço
LOOP_MIN_REPS = 3
LONG_RATIO = 1.5       # saída >= 1,5x a mediana dos outros modelos ...
LONG_EXTRA = 300       # ... e pelo menos 300 caracteres a mais
BREAKDOWNS = ("template", "level", "writing", "split")
BLOCK = re.compile(r'<div\b[^>]*?data-bbox="\s*(-?\d+)[\s,]+(-?\d+)[\s,]+(-?\d+)[\s,]+(-?\d+)\s*"[^>]*>')
LABEL = re.compile(r'data-label="([^"]*)"')
NOT_WORD = re.compile(r"[\W_]+")


# ----------------------------------------------------------------------- texto e blocos

def compact(s: str) -> str:
    """Só letras e dígitos (para campos numéricos)."""
    return NOT_WORD.sub("", s)


def gold_text(t: str) -> str:
    # gabarito é texto puro: escapa < e > para a normalização não tratá-los como tag
    return normalize(html.escape(t, quote=False))


@dataclass
class Block:
    bbox: tuple[int, int, int, int]
    label: str
    text: str


def parse_blocks(pred: str) -> list[Block]:
    """Blocos de layout do Chandra. Cada bloco vai da sua abertura até a próxima, então uma
    saída cortada no meio de um bloco ainda devolve o bloco incompleto."""
    ms = list(BLOCK.finditer(pred))
    out = []
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(pred)
        lab = LABEL.search(m.group(0))
        out.append(Block(tuple(int(m.group(k)) for k in range(1, 5)),
                         lab.group(1) if lab else "", normalize(pred[m.end():end])))
    return out


def overlaps(a, b, margin: float = 0) -> bool:
    return (a[0] - margin < b[2] and b[0] < a[2] + margin
            and a[1] - margin < b[3] and b[1] < a[3] + margin)


def _codes(s: str) -> np.ndarray:
    return np.frombuffer(s.encode("utf-32-le"), dtype=np.uint32)


def _last_row(pattern: str, t: np.ndarray, free_start: bool) -> np.ndarray:
    """Última linha da DP de edição de `pattern` contra prefixos de `t`. Com free_start o
    casamento pode começar em qualquer ponto de `t` (infixo); sem, começa em t[0]."""
    ar = np.arange(len(t) + 1, dtype=np.int64)
    prev = np.zeros(len(t) + 1, dtype=np.int64) if free_start else ar.copy()
    for i, ch in enumerate(pattern, 1):
        best = np.minimum(prev[:-1] + (t != ord(ch)), prev[1:] + 1)
        tmp = np.concatenate([[i], best])
        prev = np.minimum.accumulate(tmp - ar) + ar
    return prev


def infix_span(pattern: str, text: str) -> tuple[int, int, int]:
    """(distância, início, fim) do trecho de `text` mais parecido com `pattern`."""
    if not pattern:
        return 0, 0, 0
    if not text:
        return len(pattern), 0, 0
    t = _codes(text)
    row = _last_row(pattern, t, free_start=True)
    end = int(row.argmin())
    # o início sai da mesma conta de trás para frente, ancorada no fim encontrado
    back = _last_row(pattern[::-1], t[:end][::-1], free_start=False)
    k = int(back.argmin())
    return int(row[end]), end - k, end


def longest_repeat(text: str, max_period: int = 300) -> dict:
    """Maior trecho formado por uma unidade repetida em sequência ("abcabcabc"): período,
    caracteres repetidos depois da 1ª ocorrência, repetições e a unidade."""
    t = _codes(text)
    best = {"periodo": 0, "repetido": 0, "repeticoes": 0.0, "unidade": ""}
    for p in range(1, min(max_period, len(t) // 2) + 1):
        eq = t[p:] == t[:-p]
        if not eq.any():
            continue
        d = np.diff(np.concatenate([[0], eq.astype(np.int8), [0]]))
        starts, ends = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
        j = int(np.argmax(ends - starts))
        run = int(ends[j] - starts[j])
        if run > best["repetido"]:
            best = {"periodo": p, "repetido": run, "repeticoes": round((run + p) / p, 1),
                    "unidade": text[starts[j]:starts[j] + p][:60]}
    return best


def is_loop(rep: dict) -> bool:
    """Laço: >= LOOP_MIN_RUN caracteres repetidos, >= LOOP_MIN_REPS vezes. Unidade só de
    pontuação (pontilhado ou sublinhado de formulário) precisa de 4x mais."""
    need = LOOP_MIN_RUN if compact(rep["unidade"]) else 4 * LOOP_MIN_RUN
    return rep["repetido"] >= need and rep["repeticoes"] >= LOOP_MIN_REPS


# ----------------------------------------------------------------------- gabarito

@dataclass
class Field:
    label: str
    cls: str
    text: str          # normalizado
    cmp: str           # o que é comparado (compactado em `number`)
    box: tuple | None  # 0-1000
    stripped: bool
    short: bool = field(init=False)

    def __post_init__(self):
        self.short = len(self.cmp) <= SHORT


def page_size(row: dict, data_dir: Path) -> tuple[int, int] | None:
    if row.get("size"):
        return tuple(row["size"])
    p = data_dir / row["image"] if row.get("image") else None
    if p is None or not p.exists():
        return None
    from PIL import Image
    with Image.open(p) as im:
        return im.size


def fields_of(row: dict, size) -> list[Field]:
    out = []
    for f in row.get("fields", []):
        if f.get("kind", "manuscrito") != "manuscrito":
            continue
        g = gold_text(f["text"])
        cls = f.get("cls") or "text"
        box = f.get("bbox_1000")
        if box is None and f.get("box") and size:
            w, h = size
            x0, y0, x1, y1 = f["box"]
            box = (1000 * x0 / w, 1000 * y0 / h, 1000 * x1 / w, 1000 * y1 / h)
        out.append(Field(f.get("label", ""), cls, g, compact(g) if cls == "number" else g,
                         tuple(box) if box else None, bool(f.get("accent_stripped"))))
    return out


# ----------------------------------------------------------------------- uma página

def score_page(fields: list[Field], pred: dict, margin: float = MARGIN) -> dict:
    """Mede uma predição contra os campos de uma página. Devolve os campos medidos e os
    sinais de página (sem os que dependem dos outros modelos)."""
    text = pred.get("pred") or ""
    full = normalize(text)
    full_c = compact(full)
    blocks = parse_blocks(text)
    recs = []
    for f in fields:
        if f.stripped:
            continue
        n = max(len(f.cmp), 1)
        hay = full_c if f.cls == "number" else full
        d_free = infix_distance(f.cmp, hay)
        d_loc = None
        if f.box is not None:
            local = " ".join(b.text for b in blocks if overlaps(b.bbox, f.box, margin))
            d_loc = infix_distance(f.cmp, compact(local) if f.cls == "number" else local)
        recs.append({"label": f.label, "cls": f.cls, "n": n, "short": f.short, "box": f.box,
                     "d_livre": d_free, "d_local": d_loc,
                     "exato_livre": d_free == 0, "exato_local": d_loc == 0 if d_loc is not None else None,
                     "achado": d_free / n <= FOUND_CER})
    main = [r for r in recs if not r["short"]]
    complete = sum(r["achado"] for r in main) / len(main) if main else None

    # truncamento: os últimos campos (ordem de leitura) faltam, os primeiros estão lá e
    # nenhum bloco da saída chega à altura deles
    trunc_tail = False
    located = sorted((r for r in main if r["box"] is not None), key=lambda r: (r["box"][1], r["box"][0]))
    if len(located) >= 4:
        k = max(2, math.ceil(len(located) / 4))
        head, tail = located[:-k], located[-k:]
        reach = max((b.bbox[3] for b in blocks), default=0)
        trunc_tail = (not any(r["achado"] for r in tail)
                      and sum(r["achado"] for r in head) / len(head) >= 0.5
                      and reach < min(r["box"][1] for r in tail))
    rep = longest_repeat(full)
    return {"campos": recs, "completude": complete, "fim": pred.get("fim"),
            "truncada_fim": pred.get("fim") == "length", "truncada_cauda": trunc_tail,
            "repeticao": rep, "laco_repeticao": is_loop(rep), "chars": len(full),
            "tokens": pred.get("tokens"), "blocos": len(blocks)}


def printed_text(fields: list[Field], pred_text: str, margin: float = MARGIN) -> str:
    """Saída sem os valores manuscritos: em cada bloco que encosta num campo, apaga o
    trecho que casa com o valor (exato se for curto, CER <= ERASE_CER se não)."""
    parts = []
    for b in parse_blocks(pred_text) or [Block((0, 0, 1000, 1000), "", normalize(pred_text))]:
        t = b.text
        for f in fields:
            if f.box is None or not overlaps(b.bbox, f.box, margin) or not f.text:
                continue
            d, s, e = infix_span(f.text, t)
            if d <= (0 if f.short else ERASE_CER * len(f.text)):
                t = t[:s] + " " + t[e:]
        t = " ".join(t.split())
        if t:
            parts.append(t)
    return " ".join(parts)


# ----------------------------------------------------------------------- agregação

def _rate(recs, key):
    v = [r[key] for r in recs if r[key] is not None]
    return sum(v) / len(v) if v else None


def _cer(recs, key):
    v = [(r[key], r["n"]) for r in recs if r[key] is not None]
    return sum(d for d, _ in v) / sum(n for _, n in v) if v else None


def field_summary(recs: list[dict]) -> dict:
    return {"campos": len(recs),
            "exato_livre": _rate(recs, "exato_livre"), "cer_livre": _cer(recs, "d_livre"),
            "exato_local": _rate(recs, "exato_local"), "cer_local": _cer(recs, "d_local")}


def page_summary(pages: list[dict]) -> dict:
    comp = [p["completude"] for p in pages if p["completude"] is not None]
    return {"paginas": len(pages),
            "completude": sum(comp) / len(comp) if comp else None,
            "truncadas": sum(p["truncada"] for p in pages) / len(pages) if pages else None,
            "lacos": sum(p["laco"] for p in pages) / len(pages) if pages else None}


def summarize(pages: list[dict]) -> dict:
    recs = [r for p in pages for r in p["campos"]]
    main = [r for r in recs if not r["short"]]
    out = {"todos": field_summary(main),
           "nomes": field_summary([r for r in main if r["cls"] == "name"]),
           "curtos": field_summary([r for r in recs if r["short"]]),
           "por_classe": {c: field_summary([r for r in main if r["cls"] == c])
                          for c in sorted({r["cls"] for r in main})},
           **page_summary(pages)}
    imp = [p["impresso"] for p in pages if p.get("impresso")]
    if imp:
        tot = max(sum(r[2] for r in imp), 1)
        out["impresso_cer"] = sum(r[0] for r in imp) / tot
        out["impresso_cer_sem_caixa"] = sum(r[1] for r in imp) / tot
        out["impresso_paginas_alteradas"] = sum(r[0] > 0 for r in imp) / len(imp)
    return out


def mcnemar(b: int, c: int) -> float:
    """p-valor bilateral exato (binomial) do teste de McNemar."""
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(min(b, c) + 1))
    return min(1.0, 2 * tail / 2 ** n)


def paired(ref_pages: list[dict], cand_pages: list[dict], n_boot: int, seed: int) -> dict:
    """Candidato menos referência, nas mesmas páginas e nos mesmos campos."""
    if not ref_pages:
        return {}
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(ref_pages), size=(n_boot, len(ref_pages)))
    out = {}

    def counts(sel, key):
        e_r, e_c, n = [], [], []
        for pr, pc in zip(ref_pages, cand_pages):
            rr = [r for r in pr["campos"] if sel(r)]
            cc = [r for r in pc["campos"] if sel(r)]
            e_r.append(sum(bool(r[key]) for r in rr))
            e_c.append(sum(bool(r[key]) for r in cc))
            n.append(len(rr))
        return np.array(e_r), np.array(e_c), np.array(n)

    for name, sel in (("campos", lambda r: not r["short"]),
                      ("nomes", lambda r: not r["short"] and r["cls"] == "name")):
        for key in ("exato_livre", "exato_local"):
            e_r, e_c, n = counts(sel, key)
            if n.sum() == 0:
                continue
            delta = (e_c.sum() - e_r.sum()) / n.sum()
            bs = (e_c[idx].sum(1) - e_r[idx].sum(1)) / np.maximum(n[idx].sum(1), 1)
            # McNemar campo a campo
            b = c = 0
            for pr, pc in zip(ref_pages, cand_pages):
                for rr, cc in zip(pr["campos"], pc["campos"]):
                    if sel(rr) and rr[key] is not None and cc[key] is not None:
                        b += bool(rr[key]) and not cc[key]
                        c += bool(cc[key]) and not rr[key]
            out[f"{name}/{key}"] = {"ref": e_r.sum() / n.sum(), "cand": e_c.sum() / n.sum(),
                                   "delta": delta, "ic95": [float(np.percentile(bs, 2.5)),
                                                            float(np.percentile(bs, 97.5))],
                                   "campos": int(n.sum()), "so_ref": b, "so_cand": c,
                                   "mcnemar_p": mcnemar(b, c)}
    keep = [i for i, (a, b) in enumerate(zip(ref_pages, cand_pages))
            if a["completude"] is not None and b["completude"] is not None]
    if keep:
        cr = np.array([ref_pages[i]["completude"] for i in keep])
        cc = np.array([cand_pages[i]["completude"] for i in keep])
        j = rng.integers(0, len(keep), size=(n_boot, len(keep)))
        bs = (cc[j] - cr[j]).mean(1)
        out["completude"] = {"ref": cr.mean(), "cand": cc.mean(), "delta": (cc - cr).mean(),
                             "ic95": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))],
                             "paginas": len(keep)}
    return out


# ----------------------------------------------------------------------- conjunto

def evaluate(gold_rows: list[dict], preds: dict[str, dict[str, dict]], data_dir: Path,
             ref: str | None = "base", n_boot: int = 1000, seed: int = 42,
             margin: float = MARGIN) -> dict:
    """gold_rows: linhas do pages.jsonl; preds: {modelo: {id: predição}}. Só entram as
    páginas com gabarito e predição de todos os modelos."""
    models = list(preds)
    gold = {r["id"]: r for r in gold_rows}
    ids = [i for i in gold if all(i in preds[m] for m in models)]
    skipped = {m: sorted(set(preds[m]) - set(gold)) for m in models}
    per_model: dict[str, list[dict]] = {m: [] for m in models}
    n_stripped = 0
    for pid in ids:
        row = gold[pid]
        flds = fields_of(row, page_size(row, data_dir))
        n_stripped += sum(f.stripped for f in flds)
        meta = {k: row.get(k) for k in BREAKDOWNS if row.get(k) is not None}
        scored = {m: score_page(flds, preds[m][pid], margin) for m in models}
        printed = ({m: printed_text(flds, preds[m][pid].get("pred") or "", margin) for m in models}
                   if ref in models else {})
        for m in models:
            p = scored[m]
            others = [scored[o]["chars"] for o in models if o != m]
            med = float(np.median(others)) if others else None
            p["longa"] = bool(med is not None and p["chars"] >= LONG_RATIO * med
                              and p["chars"] - med >= LONG_EXTRA)
            p["laco"] = p["laco_repeticao"] or p["longa"]
            p["truncada"] = p["truncada_fim"] or p["truncada_cauda"]
            if printed and m != ref:
                a, b = printed[ref], printed[m]
                p["impresso"] = (edit_distance(a, b), edit_distance(a.casefold(), b.casefold()), len(a))
            p.update(id=pid, **meta)
            per_model[m].append(p)

    out = {"paginas": len(ids), "modelos": models, "referencia": ref,
           "predicoes_sem_gabarito": {m: len(v) for m, v in skipped.items()},
           "campos_sem_acento_ignorados": n_stripped,
           "resumo": {m: summarize(per_model[m]) for m in models}, "pareado": {}, "recortes": {}}
    if ref in models:
        for m in models:
            if m != ref:
                out["pareado"][m] = paired(per_model[ref], per_model[m], n_boot, seed)
    for key in BREAKDOWNS:
        vals = sorted({p[key] for p in per_model[models[0]] if key in p}, key=str) if models else []
        if not vals:
            continue
        out["recortes"][key] = {str(v): {m: summarize([p for p in per_model[m] if p.get(key) == v])
                                         for m in models} for v in vals}
    out["por_pagina"] = {m: [{k: v for k, v in p.items() if k != "campos"} for p in per_model[m]]
                         for m in models}
    out["por_campo"] = {m: [{"id": p["id"], **{k: v for k, v in r.items() if k != "box"}}
                            for p in per_model[m] for r in p["campos"]] for m in models}
    return out


# ----------------------------------------------------------------------- relatório

def _pct(x, nd=1) -> str:
    return "-" if x is None else f"{100 * x:.{nd}f}"


def _ci(ci) -> str:
    return f"[{100 * ci[0]:+.1f}, {100 * ci[1]:+.1f}]"


def report(res: dict, name: str) -> str:
    models, ref = res["modelos"], res["referencia"]
    S = res["resumo"]
    skipped = ", ".join(f"{m} {n}" for m, n in res["predicoes_sem_gabarito"].items() if n)
    L = [f"# Avaliação de páginas inteiras: {name}", "",
         f"{res['paginas']} páginas com gabarito e predição de todos os modelos"
         + (f" (predições sem gabarito ignoradas: {skipped})" if skipped else "") + ". "
         f"{res['campos_sem_acento_ignorados']} campos cuja tinta perdeu os acentos ficam de fora. "
         f"Campos de até {SHORT} caracteres vão para uma tabela à parte. Valores em %.", "",
         "Livre: o valor pode estar em qualquer ponto da saída. Local: só nos blocos cuja caixa "
         "encosta na do campo. CER = distância de edição / tamanho do campo. "
         "Campos numéricos comparados só por letras e dígitos.", "",
         "## Campos manuscritos", "",
         "| Modelo | Campos | Exatos livre | CER livre | Exatos local | CER local "
         "| Nomes | Nomes exatos livre | Nomes exatos local | Nomes CER local |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for m in models:
        a, n = S[m]["todos"], S[m]["nomes"]
        L.append(f"| {m} | {a['campos']} | {_pct(a['exato_livre'])} | {_pct(a['cer_livre'])} | "
                 f"{_pct(a['exato_local'])} | {_pct(a['cer_local'])} | {n['campos']} | "
                 f"{_pct(n['exato_livre'])} | {_pct(n['exato_local'])} | {_pct(n['cer_local'])} |")
    L += ["", "### Por classe de campo", "",
          "| Classe | Modelo | Campos | Exatos livre | CER livre | Exatos local | CER local |",
          "|---|---|---|---|---|---|---|"]
    for c in sorted({c for m in models for c in S[m]["por_classe"]}):
        for m in models:
            a = S[m]["por_classe"].get(c)
            if a:
                L.append(f"| {c} | {m} | {a['campos']} | {_pct(a['exato_livre'])} | {_pct(a['cer_livre'])} | "
                         f"{_pct(a['exato_local'])} | {_pct(a['cer_local'])} |")
    L += ["", f"### Campos curtos (até {SHORT} caracteres, fora dos totais)", "",
          "| Modelo | Campos | Exatos livre | Exatos local |", "|---|---|---|---|"]
    for m in models:
        a = S[m]["curtos"]
        L.append(f"| {m} | {a['campos']} | {_pct(a['exato_livre'])} | {_pct(a['exato_local'])} |")
    L += ["", "## Página", "",
          f"Completude: fração dos campos achados com CER <= {FOUND_CER:.1f} (livre). Truncada: "
          "`fim = length` ou últimos campos ausentes sem bloco na altura deles. Laço: trecho "
          f"repetido em sequência (>= {LOOP_MIN_RUN} caracteres, >= {LOOP_MIN_REPS} vezes) ou saída "
          f">= {LONG_RATIO}x a dos outros modelos. Impresso: CER entre a saída do modelo e a da "
          f"referência ({ref}) depois de apagar os valores manuscritos.", "",
          "| Modelo | Páginas | Completude | Truncadas | Laços | Impresso CER vs ref "
          "| Idem, sem maiúsc./minúsc. | Páginas com impresso alterado |",
          "|---|---|---|---|---|---|---|---|"]
    for m in models:
        s = S[m]
        L.append(f"| {m} | {s['paginas']} | {_pct(s['completude'])} | {_pct(s['truncadas'])} | "
                 f"{_pct(s['lacos'])} | {_pct(s.get('impresso_cer'), 2)} | "
                 f"{_pct(s.get('impresso_cer_sem_caixa'), 2)} | {_pct(s.get('impresso_paginas_alteradas'))} |")
    if res["pareado"]:
        L += ["", f"## Comparação pareada com {ref}", "",
              "Diferença em pontos percentuais (modelo - referência) nas mesmas páginas e campos; "
              "IC de 95% por bootstrap pareado sobre páginas; McNemar exato campo a campo "
              "(só ref = acertos só da referência, só modelo = acertos só do modelo).", "",
              "| Modelo | Métrica | Ref | Modelo | Diferença | IC 95% | Só ref / só modelo | McNemar p |",
              "|---|---|---|---|---|---|---|---|"]
        for m, P in res["pareado"].items():
            for key, v in P.items():
                mc = (f"{v['so_ref']} / {v['so_cand']} | {v['mcnemar_p']:.3g}" if "mcnemar_p" in v
                      else "- | -")
                L.append(f"| {m} | {key} | {_pct(v['ref'])} | {_pct(v['cand'])} | "
                         f"{100 * v['delta']:+.1f} | {_ci(v['ic95'])} | {mc} |")
    for key, groups in res["recortes"].items():
        L += ["", f"## Por {key}", "",
              f"| {key} | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local "
              "| Completude | Truncadas | Laços |", "|---|---|---|---|---|---|---|---|---|---|"]
        for v, per in groups.items():
            for m in models:
                s = per[m]
                L.append(f"| {v} | {m} | {s['paginas']} | {s['todos']['campos']} | "
                         f"{_pct(s['todos']['exato_livre'])} | {_pct(s['todos']['exato_local'])} | "
                         f"{_pct(s['nomes']['exato_local'])} | {_pct(s['completude'])} | "
                         f"{_pct(s['truncadas'])} | {_pct(s['lacos'])} |")
    return "\n".join(L) + "\n"


def load_preds(path: Path) -> dict[str, dict]:
    return {r["id"]: r for r in map(json.loads, open(path, encoding="utf-8"))}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--set", default="ocrsd", help="conjunto em data/pages/<set>/pages.jsonl")
    ap.add_argument("--models", nargs="+",
                    help="pastas em experiments/paginas/ (padrão: todas com <set>.jsonl, ref primeiro)")
    ap.add_argument("--ref", default="base", help="modelo de referência da comparação pareada")
    ap.add_argument("--boot", type=int, default=1000)
    ap.add_argument("--margin", type=float, default=MARGIN)
    args = ap.parse_args()
    cfg = load_config(args.config)
    data_dir = resolve(cfg, "raw").parent
    root = resolve(cfg, "experiments") / "paginas"
    models = args.models or sorted((p.parent.name for p in root.glob(f"*/{args.set}.jsonl")),
                                   key=lambda m: (m != args.ref, m))
    missing = [m for m in models if not (root / m / f"{args.set}.jsonl").exists()]
    if missing:
        raise SystemExit(f"sem predições para {missing} em {root}/<modelo>/{args.set}.jsonl")
    gold = [json.loads(l) for l in open(data_dir / "pages" / args.set / "pages.jsonl", encoding="utf-8")]
    preds = {m: load_preds(root / m / f"{args.set}.jsonl") for m in models}
    res = evaluate(gold, preds, data_dir, args.ref, args.boot, cfg["seed"], args.margin)
    res["conjunto"] = args.set
    md = report(res, args.set)
    (root / f"avaliacao_{args.set}.md").write_text(md, encoding="utf-8")
    (root / f"avaliacao_{args.set}.json").write_text(
        json.dumps(res, indent=1, ensure_ascii=False, default=float), encoding="utf-8")
    print(md)
    print(f"-> {root / f'avaliacao_{args.set}.md'}")


if __name__ == "__main__":
    main()
