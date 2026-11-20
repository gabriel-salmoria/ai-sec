"""Gabarito de página inteira no formato nativo do Chandra, com pesos por trecho.

O texto impresso de cada modelo vem da transcrição do próprio Chandra (base) do formulário,
guardada em data/forms/<modelo>/printed.json como blocos {bbox, label, html}. Cada campo
manuscrito vira um bloco próprio, inserido logo depois do bloco impresso que é o seu
rótulo (como o Chandra faz: "Nome" e, em seguida, o nome). Os trechos manuscritos recebem
peso 1 na perda; o resto (impresso, tags, caixas) recebe `W_PRINTED`; campos cuja tinta
perdeu acentos (escrita neural do OCRSD) recebem peso 0.

    python -m ocr06.forms.targets derive          # printed_from_preds.json a partir das predições base existentes
    python -m ocr06.forms.targets from-blank      # printed.json a partir do Chandra base nos modelos em branco
    python -m ocr06.forms.targets build --set forms_v1 --out data/final/pages_v1
"""
from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
W_PRINTED = 0.3
W_CLASS = {"name": 2.0}  # nomes pesam o dobro na perda
BLOCK = re.compile(r'<div data-bbox="(\d+) (\d+) (\d+) (\d+)" data-label="([^"]+)">(.*?)</div>', re.S)
TAG = re.compile(r"<[^>]+>")


def blocks_of(pred: str) -> list[dict]:
    return [{"bbox": [int(m[i]) for i in range(1, 5)], "label": m[5], "html": m[6].strip()}
            for m in BLOCK.finditer(pred)]


def plain(h: str) -> str:
    return " ".join(html.unescape(TAG.sub(" ", h)).split())


def _cer(a: str, b: str) -> float:
    if not a:
        return 1.0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
        prev = cur
    return prev[-1] / max(len(a), 1)


def derive_printed(template: str) -> list[dict] | None:
    """Blocos impressos tirados das predições do Chandra base em páginas do OCRSD com esse
    modelo: tudo que não casa com nenhum valor manuscrito do gabarito."""
    gold = {}
    for l in open(ROOT / "data" / "pages" / "ocrsd" / "pages.jsonl", encoding="utf-8"):
        r = json.loads(l)
        if r["template"] == template and r["writing"] == "font":
            gold[r["id"]] = r
    best = None
    for l in open(ROOT / "experiments" / "paginas" / "base" / "ocrsd.jsonl", encoding="utf-8"):
        p = json.loads(l)
        if p["id"] not in gold:
            continue
        vals = [f["text"] for f in gold[p["id"]]["fields"]]
        printed = [b for b in blocks_of(p["pred"])
                   if not any(_cer(v, plain(b["html"])) < 0.35 for v in vals if len(v) > 1)
                   and plain(b["html"]) not in vals]
        if best is None or len(printed) > len(best):
            best = printed
    return best


def _label_for(value_box, printed):
    """Bloco impresso que rotula o campo: logo acima (ou à esquerda) e sobreposto em x."""
    x0, y0, x1, y1 = value_box
    best, dist = None, 1e9
    for i, b in enumerate(printed):
        bx0, by0, bx1, by1 = b["bbox"]
        overlap = min(x1, bx1) - max(x0, bx0)
        if by1 <= y0 + 8 and overlap > 0 and y0 - by1 < 40:
            d = y0 - by1
        elif abs((by0 + by1) / 2 - (y0 + y1) / 2) < 12 and bx1 <= x0 + 5:
            d = 20 + x0 - bx1
        else:
            continue
        if d < dist:
            best, dist = i, d
    return best


def build_target(fields: list[dict], printed: list[dict], italic: bool = False) -> tuple[str, list[dict]]:
    """fields: [{text, bbox_1000, accent_stripped?}] -> (html, spans)."""
    def overlaps(a, b):
        return min(a[2], b[2]) - max(a[0], b[0]) > 0 and min(a[3], b[3]) - max(a[1], b[1]) > 0
    # Blocos que descrevem campo vazio ("[Campo vazio]") saem quando o campo foi escrito;
    # blocos só de dígitos são valores da página de onde o impresso foi tirado.
    printed = [b for b in printed
               if not (plain(b["html"]).startswith("[") and any(overlaps(b["bbox"], f["bbox_1000"]) for f in fields))
               and not (re.fullmatch(r"[\d\s.\-/]{6,}", plain(b["html"])))]
    after: dict[int | None, list[dict]] = {}
    for f in sorted(fields, key=lambda f: (f["bbox_1000"][1], f["bbox_1000"][0])):
        after.setdefault(_label_for(f["bbox_1000"], printed), []).append(f)
    out, spans = [], []
    pos = 0

    def emit(s: str):
        nonlocal pos
        out.append(s)
        pos += len(s)

    def emit_value(f):
        b = f["bbox_1000"]
        emit(f'<div data-bbox="{b[0]} {b[1]} {b[2]} {b[3]}" data-label="Text"><p>' + ("<i>" if italic else ""))
        t = html.escape(f["text"], quote=False)
        spans.append({"start": pos, "end": pos + len(t),
                      "w": 0.0 if f.get("accent_stripped") else W_CLASS.get(f.get("cls"), 1.0)})
        emit(t)
        emit(("</i>" if italic else "") + "</p></div>")

    orphans = after.pop(None, [])
    for i, b in enumerate(printed):
        # campos sem rótulo identificado entram na posição de leitura (y, x)
        while orphans and (orphans[0]["bbox_1000"][1], orphans[0]["bbox_1000"][0]) < (b["bbox"][1], b["bbox"][0]):
            emit_value(orphans.pop(0))
        bb = b["bbox"]
        emit(f'<div data-bbox="{bb[0]} {bb[1]} {bb[2]} {bb[3]}" data-label="{b["label"]}">{b["html"]}</div>')
        for f in after.get(i, []):
            emit_value(f)
    for f in orphans:
        emit_value(f)
    return "".join(out), spans


def printed_for(template: str) -> list[dict] | None:
    """printed.json (Chandra base no modelo em branco) tem prioridade; senão, o derivado."""
    for name in ("printed.json", "printed_from_preds.json"):
        path = ROOT / "data" / "forms" / template / name
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    return None


def ocrsd_level(r: dict) -> int:
    """Nível de dificuldade de uma página do OCRSD (para o currículo)."""
    if r["writing"] == "font":
        lv = 1
    else:
        b = r.get("bias") if r.get("bias") is not None else 0.75
        lv = 2 if b >= 0.7 else 3 if b >= 0.45 else 4
    return min(lv + (r.get("filter") == "strong"), 4)


def training_rows(sets: list[str]) -> tuple[list[dict], dict]:
    from PIL import Image
    prompt = (ROOT / "configs" / "prompt_chandra_layout.txt").read_text(encoding="utf-8").strip()
    rows, missing = [], {}
    for name in sets:
        for l in open(ROOT / "data" / "pages" / name / "pages.jsonl", encoding="utf-8"):
            r = json.loads(l)
            printed = printed_for(r["template"])
            if printed is None:
                missing[r["template"]] = missing.get(r["template"], 0) + 1
                continue
            if "size" in r:
                w, h = r["size"]
            else:
                w, h = Image.open(ROOT / "data" / r["image"]).size
            fields = []
            for f in r["fields"]:
                b = f.get("bbox_1000") or [round(1000 * f["box"][0] / w), round(1000 * f["box"][1] / h),
                                           round(1000 * f["box"][2] / w), round(1000 * f["box"][3] / h)]
                fields.append({"text": f["text"], "bbox_1000": b, "accent_stripped": f.get("accent_stripped", False)})
            target, spans = build_target(fields, printed)
            rows.append({"id": r["id"], "source": "ocrsd" if name == "ocrsd" else "local", "image": r["image"],
                         "template": r["template"], "split": r.get("split", "train"),
                         "level": r["level"] if "level" in r else ocrsd_level(r),
                         "messages": [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt}]},
                                      {"role": "assistant", "content": [{"type": "text", "text": target}]}],
                         "spans": spans, "w_default": W_PRINTED})
    return rows, missing


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["derive", "build", "from-blank", "build2", "build3"])
    ap.add_argument("--sets", nargs="+", default=["ocrsd"])
    ap.add_argument("--out", default="data/final/pages_v1")
    a = ap.parse_args()
    if a.cmd == "build3":  # 2ª etapa: 1.559 páginas locais novas + as 141 OCRSD que a 1ª não viu
        build_v2(a.out, sources=(("forms_v2", "train"), ("ocrsd", "test")), limits={"forms_v2": 1559})
        return
    if a.cmd == "build2":
        build_v2(a.out)
        return
    if a.cmd == "from-blank":
        # Saída do Chandra base nos modelos em branco (GPU): o texto impresso de cada modelo.
        src = ROOT / "experiments" / "paginas" / "base" / "modelos_em_branco.jsonl"
        for l in open(src, encoding="utf-8"):
            p = json.loads(l)
            blocks = blocks_of(p["pred"])
            path = ROOT / "data" / "forms" / p["id"] / "printed.json"
            path.write_text(json.dumps(blocks, ensure_ascii=False, indent=1), encoding="utf-8")
            print(p["id"], len(blocks), "blocos ->", path)
        return
    if a.cmd == "build":
        rows, missing = training_rows(a.sets)
        out = ROOT / a.out
        out.mkdir(parents=True, exist_ok=True)
        for split in ("train", "test"):
            with open(out / f"{split}.jsonl", "w", encoding="utf-8") as fh:
                for r in rows:
                    if r["split"] == split:
                        fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(len(rows), "páginas ->", out, "| sem texto impresso do modelo (precisa do Chandra):", missing)
        return
    if a.cmd == "derive":
        for t in ("certidao_casamento", "certidao_obito", "certidao_casamento_cnj",
                  "certidao_nascimento_cnj", "dnv"):
            pr = derive_printed(t)
            path = ROOT / "data" / "forms" / t / "printed_from_preds.json"
            if pr:
                path.write_text(json.dumps(pr, ensure_ascii=False, indent=1), encoding="utf-8")
            print(t, "blocos impressos:", len(pr) if pr else "sem predições do Chandra base (precisa da GPU)")



# ----------------------------------------------------------------------------- v2 (após a sessão 1)
import unicodedata as _ud

_STOP = {"de", "da", "do", "das", "dos", "e", "o", "a", "se", "em", "ou", "por", "para", "n", "no", "na"}


def _toks(s: str) -> set[str]:
    s = "".join(c for c in _ud.normalize("NFD", plain(s).lower()) if not _ud.combining(c))
    return {t for t in re.findall(r"[a-z]{2,}", s) if t not in _STOP}


def derive_printed_v2(template: str) -> tuple[list[dict] | None, bool, int]:
    """Texto impresso a partir das saídas do Chandra base em PÁGINAS PREENCHIDAS do modelo
    (sessão 1): para cada página, os blocos que não casam com nenhum valor manuscrito;
    fica a página com o número mediano de blocos (evita páginas com sobras). Devolve também
    se o Chandra costuma pôr o manuscrito em itálico nesse modelo."""
    cands, ital, vals_n = [], 0, 0
    for gold_set, pred_file in (("teste_local", "base/teste_local.jsonl"), ("teste_ocrsd", "base/teste_ocrsd.jsonl")):
        gp = ROOT / "data" / "pages" / gold_set / "pages.jsonl"
        pp = ROOT / "experiments" / "paginas" / pred_file
        if not gp.exists() or not pp.exists():
            continue
        gold = {json.loads(l)["id"]: json.loads(l) for l in open(gp, encoding="utf-8")}
        for l in open(pp, encoding="utf-8"):
            p = json.loads(l)
            g = gold.get(p["id"])
            if not g or g["template"] != template or p.get("fim") != "stop":
                continue
            vals = [f["text"] for f in g["fields"] if len(f["text"]) > 1]
            printed = []
            for b in blocks_of(p["pred"]):
                t = plain(b["html"])
                if any(_cer(v, t) < 0.35 for v in vals) or t in vals:
                    vals_n += 1
                    ital += "<i>" in b["html"]
                elif not re.fullmatch(r"[\d\s.\-/]{6,}", t):
                    printed.append(b)
            cands.append(printed)
    if not cands:
        return None, False, 0
    # Consenso: o impresso se repete em todas as páginas; valor mal lido não. Fica só o bloco
    # cujo texto (sem dígitos) aparece em pelo menos metade das páginas; dígitos que o
    # Chandra juntou ao rótulo ("Dia 10") saem.
    from collections import Counter
    key = lambda b: re.sub(r"[\d\s_]+", " ", plain(b["html"])).strip().lower()
    freq = Counter(k for c in cands for k in {key(b) for b in c})
    keep = lambda b: key(b) and freq[key(b)] >= len(cands) / 2
    cands.sort(key=len)
    chosen = []
    for b in cands[len(cands) // 2]:
        if keep(b) or b["label"] == "Image":
            h = b["html"] if b["label"] == "Image" else re.sub(r"\s*\b\d+\b", "", b["html"])
            chosen.append({**b, "html": h})
    return chosen, (ital / vals_n > 0.5 if vals_n else False), len(cands)


def _dnv_value(text: str, label: str) -> str:
    """Formato que o Chandra usa nas caixinhas de dígito do DNV (datas em grupos)."""
    if re.fullmatch(r"\d{8}", text) and "data" in label.lower():
        return f"{text[:2]} {text[2:4]} {text[4:]}"
    if re.fullmatch(r"\d{4}", text) and "hora" in label.lower():
        return f"{text[:2]} {text[2:]}"
    return text


def build_dnv_target(fields: list[dict], blank_pred: str, mapping: dict) -> tuple[str, list[dict], float]:
    """DNV: o Chandra transcreve o formulário como uma tabela HTML. Cada valor manuscrito
    entra na célula cujo texto mais se parece com o rótulo do campo (no mapeamento), em
    itálico, depois do texto impresso; caixas marcadas viram `checked`. Devolve também a
    fração de campos que acharam célula (página fica fora do treino se for baixa)."""
    cells = list(re.finditer(r"(<td[^>]*>)(.*?)(</td>)", blank_pred, re.S))
    cell_toks = [_toks(m.group(2)) for m in cells]
    lead = [(re.match(r"\s*(\d+)", plain(m.group(2))) or [None, None])[1] for m in cells]
    add: dict[int, list] = {}
    found = 0
    for f in fields:
        fid = f.get("field_id") or f.get("label")
        lab = mapping.get(fid, {}).get("label", "")
        lt = _toks(lab)
        if not lt:
            continue
        num = re.match(r"\d+", str(fid))
        num = num.group(0) if num else None
        score = [len(lt & ct) / len(lt) + (0.5 if num and lead[i] == num else 0) for i, ct in enumerate(cell_toks)]
        # empate: a célula mais específica (menos palavras) ganha
        best = max(range(len(cells)), key=lambda i: (score[i], -len(cell_toks[i]))) if cells else None
        if best is None or score[best] < 0.5:
            continue
        found += 1
        add.setdefault(best, []).append((f, lab))
    out, spans, pos, last = [], [], 0, 0

    def emit(s):
        nonlocal pos
        out.append(s)
        pos += len(s)

    for i, m in enumerate(cells):
        emit(blank_pred[last:m.start(2)])
        inner = m.group(2)
        for f, lab in add.get(i, []):
            if f.get("cls") == "closed" and f.get("hand") == "mark":
                for opt in f["text"].split("; "):
                    ot = _toks(opt)
                    for im in re.finditer(r"<input([^>]*)/?>([^<]*)", inner):
                        if ot and ot <= _toks(im.group(2)) and "checked" not in im.group(1):
                            inner = inner[:im.start()] + '<input checked="" type="checkbox"/>' + inner[im.end(1) + (1 if im.group(0).endswith("/>") else 0) + 1:] if False else \
                                inner.replace(im.group(0), '<input checked="" type="checkbox"/>' + im.group(2), 1)
                            break
        # valores escritos (não marcas): depois do texto impresso da célula
        pre = inner
        emit(pre)
        for f, lab in add.get(i, []):
            if f.get("cls") == "closed" and f.get("hand") == "mark":
                continue
            emit("<br/><i>")
            t = html.escape(_dnv_value(f["text"], lab), quote=False)
            spans.append({"start": pos, "end": pos + len(t),
                      "w": 0.0 if f.get("accent_stripped") else W_CLASS.get(f.get("cls"), 1.0)})
            emit(t)
            emit("</i>")
        last = m.end(2)
    emit(blank_pred[last:])
    text = "".join(out)
    for mm in re.finditer(r'<input checked="" type="checkbox"/>', text):  # marcas: peso 1
        spans.append({"start": mm.start(), "end": mm.end(), "w": 1.0})
    spans.sort(key=lambda s: s["start"])
    return text, spans, found / max(len(fields), 1)


def build_v2(out: str, seed: int = 7, n_val: int = 40,
             sources=(("forms_v1", "train"), ("ocrsd", "train")), limits=None) -> None:
    """Arquivos de treino das páginas: locais (forms_v1, partição train) + OCRSD (train).
    Certidões: impresso tirado das saídas do Chandra em páginas preenchidas; DNV: tabela."""
    import random
    from PIL import Image
    from .records import mapping_fields
    prompt = (ROOT / "configs" / "prompt_chandra_layout.txt").read_text(encoding="utf-8").strip()
    printed, italic = {}, {}
    for t in ("certidao_casamento", "certidao_casamento_cnj", "certidao_nascimento_cnj", "certidao_obito"):
        printed[t], italic[t], _ = derive_printed_v2(t)
        (ROOT / "data" / "forms" / t / "printed_v2.json").write_text(json.dumps(printed[t], ensure_ascii=False, indent=1))
    blank = {json.loads(l)["id"]: json.loads(l)["pred"]
             for l in open(ROOT / "experiments" / "paginas" / "base" / "modelos_em_branco.jsonl", encoding="utf-8")}
    rows, stats = [], {"skipped_dnv": 0, "too_few_fields": 0}
    for name, want in sources:
        src = sorted((json.loads(l) for l in open(ROOT / "data" / "pages" / name / "pages.jsonl", encoding="utf-8")),
                     key=lambda r: r["id"])
        src = [r for r in src if want == "all" or r.get("split", "train") == want]
        src = src[:(limits or {}).get(name)]  # None = todas
        for r in src:
            w, h = r.get("size") or Image.open(ROOT / "data" / r["image"]).size
            fields = []
            for f in r["fields"]:
                b = f.get("bbox_1000") or [round(1000 * f["box"][0] / w), round(1000 * f["box"][1] / h),
                                           round(1000 * f["box"][2] / w), round(1000 * f["box"][3] / h)]
                fields.append({**f, "field_id": f.get("field_id") or f.get("label"), "bbox_1000": b,
                               "hand": f.get("hand") or ("mark" if f.get("cls") == "closed" and "; " in f["text"] else "pen")})
            if len(fields) < 3:
                stats["too_few_fields"] += 1
                continue
            if r["template"] == "dnv":
                target, spans, frac = build_dnv_target(fields, blank["dnv"], mapping_fields("dnv"))
                if frac < 0.85:
                    stats["skipped_dnv"] += 1
                    continue
            else:
                target, spans = build_target(fields, printed[r["template"]], italic[r["template"]])
            lv = r["level"] if "level" in r else ocrsd_level(r)
            if name == "ocrsd":  # mesma imagem que o modelo vê (lado maior 2048), menor no upload
                dst = ROOT / "data" / "pages" / "ocrsd_2048" / "images" / Path(r["image"]).name
                if not dst.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    im = Image.open(ROOT / "data" / r["image"]).convert("RGB")
                    f = 2048 / max(im.size)
                    im.resize((round(im.width * f), round(im.height * f)), Image.LANCZOS).save(dst, quality=95)
                r = {**r, "image": f"pages/ocrsd_2048/images/{dst.name}"}
            rows.append({"id": r["id"], "source": "ocrsd" if name == "ocrsd" else "local", "image": r["image"],
                         "template": r["template"], "level": lv,
                         "messages": [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt}]},
                                      {"role": "assistant", "content": [{"type": "text", "text": target}]}],
                         "spans": spans, "w_default": W_PRINTED})
    rng = random.Random(seed)
    rng.shuffle(rows)
    # validação = amostra fixa das páginas de treino (só acompanha), metade de cada fonte
    by = {s: [r for r in rows if r["source"] == s] for s in ("local", "ocrsd")}
    val, train = by["local"][:n_val // 2] + by["ocrsd"][:n_val // 2], rows
    d = ROOT / out
    d.mkdir(parents=True, exist_ok=True)
    for split, rs in (("train", train), ("val", val)):
        with open(d / f"{split}.jsonl", "w", encoding="utf-8") as fh:
            for r in rs:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    from collections import Counter
    print(f"{len(train)} treino + {len(val)} validação -> {d}", stats)
    print(Counter((r["source"], r["template"]) for r in train))
    print("italico por modelo:", italic)


if __name__ == "__main__":
    main()
