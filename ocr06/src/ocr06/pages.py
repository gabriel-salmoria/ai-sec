"""Teste de página inteira: formulários reais com campos preenchidos à mão.

Não achamos conjunto público em português com páginas reais que misturem texto impresso e
manuscrito. Então partimos dos 50 formulários reais de validação do XFUND-PT (SUS,
Receita Federal etc.; CC BY-NC-SA 4.0, só para teste) e reescrevemos os campos
preenchidos ("answer") à mão: o texto digitado é apagado e o mesmo texto é desenhado com
o renderizador sintético, usando apenas as fontes reservadas ao teste (nunca vistas no
treino). O resto da página (rótulos, títulos, tabelas) continua sendo o impresso original.

A página vai inteira para o modelo, com o prompt nativo do Chandra (layout). Como a ordem
de leitura de um formulário é ambígua, cada campo é procurado na saída inteira: distância
de edição entre o campo e o trecho mais parecido da saída (alinhamento "infixo"). Isso
mede, na mesma página, se o manuscrito melhorou e se o impresso continua igual.

    python -m ocr06.pages build    # baixa o XFUND-PT (val) e gera data/pages/xfund_hw/
    python -m ocr06.pages score    # pontua experiments/paginas/<modelo>/xfund_hw.jsonl
    python -m ocr06.pages score --set ocrsd   # mesmo critério nas certidões sintéticas do OCRSD
"""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

import cv2
import numpy as np

from .common import download, load_config, resolve, stable_int
from .evaluate import normalize

XFUND = "https://github.com/doc-analysis/XFUND/releases/download/v1.0/"
NAME = "xfund_hw"
LONG_SIDE = 2048           # páginas A4 de 300 dpi (2480x3508) reduzidas para ~1448x2048
INK = [(25, 25, 25), (120, 40, 15), (80, 25, 10)]  # BGR: preto, azul caneta, azul escuro


def _clean(t: str) -> str:
    return " ".join(t.split())


_CMAPS: dict[str, set[int]] = {}


def _has_glyphs(font: str, text: str) -> bool:
    """A fonte tem todos os caracteres? (sem isso sairia um quadrado no lugar)."""
    if font not in _CMAPS:
        from fontTools.ttLib import TTFont
        _CMAPS[font] = set(TTFont(font).getBestCmap())
    return all(ord(c) in _CMAPS[font] for c in text if not c.isspace())


def _erase(page: np.ndarray, box: list[int]) -> None:
    """Apaga o texto digitado: pinta a caixa com a cor mediana do papel ao redor."""
    h, w = page.shape[:2]
    x0, y0, x1, y1 = box
    m = 6
    X0, Y0, X1, Y1 = max(x0 - m, 0), max(y0 - m, 0), min(x1 + m, w), min(y1 + m, h)
    ring = page[Y0:Y1, X0:X1].reshape(-1, 3)
    ring = ring[ring.sum(1) > 3 * 150]  # só papel (ignora tinta e linhas da tabela)
    color = np.median(ring, axis=0) if len(ring) else np.array([255, 255, 255])
    page[max(y0 - 2, 0):min(y1 + 2, h), max(x0 - 2, 0):min(x1 + 2, w)] = color.astype(np.uint8)


def _write_by_hand(page: np.ndarray, box: list[int], text: str, font: str, script: bool,
                   rc: dict, rng: np.random.Generator) -> bool:
    """Apaga o campo digitado e desenha `text` à mão no lugar (centrado na altura da
    caixa). Devolve False (e não mexe na página) se a fonte não tem algum caractere."""
    if not _has_glyphs(font, text):
        return False
    from .render import render_line
    h_page, w_page = page.shape[:2]
    x0, y0, x1, y1 = box
    bh = max(y1 - y0, 12)
    rc = dict(rc)
    hh = int(bh * rng.uniform(1.2, 1.5))  # a letra de mão costuma passar da altura do digitado
    rc["height"] = [hh, hh]
    rc["margin"] = [2, 4]
    try:
        _, alpha, _ = render_line(text, font, rc, rng, script)
    except ValueError:
        return False
    _erase(page, box)
    # Cabe no espaço do campo (com folga): mais largo invadiria as células vizinhas.
    room = min(w_page - x0 - 20, int((x1 - x0) * 1.3) + 10)
    if alpha.shape[1] > room:  # não cabe: reduz
        s = room / alpha.shape[1]
        alpha = cv2.resize(alpha, (room, max(1, int(alpha.shape[0] * s))), interpolation=cv2.INTER_AREA)
    ah, aw = alpha.shape
    top = int((y0 + y1) / 2 - ah / 2)
    top = min(max(top, 0), h_page - ah)
    left = max(x0 - 4, 0)
    a = (alpha.astype(np.float32) / 255.0)[..., None]
    ink = np.array(INK[rng.integers(len(INK))], np.float32)
    region = page[top:top + ah, left:left + aw].astype(np.float32)
    page[top:top + ah, left:left + aw] = (region * (1 - a) + ink * a).astype(np.uint8)
    return True


def build(cfg: dict) -> Path:
    from .fonts import fonts_for_split
    raw = resolve(cfg, "raw") / "xfund"
    zpath = download(XFUND + "pt.val.zip", raw / "pt.val.zip")
    jpath = download(XFUND + "pt.val.json", raw / "pt.val.json")
    img_dir = raw / "pt.val"
    if not img_dir.exists():
        with zipfile.ZipFile(zpath) as z:
            z.extractall(img_dir)
    docs = json.loads(jpath.read_text(encoding="utf-8"))["documents"]

    fonts = fonts_for_split(cfg, "test")
    script = {f.replace(" ", "") for f in cfg["fonts"].get("script", [])}
    out = resolve(cfg, "raw").parent / "pages" / NAME
    (out / "images").mkdir(parents=True, exist_ok=True)
    rows = []
    for doc in docs:
        page = cv2.imread(str(img_dir / doc["img"]["fname"]))
        rng = np.random.default_rng(stable_int(cfg["seed"], "pagina", doc["id"]))
        # Uma "pessoa" preenche o formulário inteiro: mesma fonte em todos os campos.
        font = fonts[rng.integers(len(fonts))]
        fields = []
        for e in doc["document"]:
            text = _clean(e["text"])
            if not text:
                continue
            kind = "impresso"
            if e["label"] == "answer" and _write_by_hand(
                    page, e["box"], text, font, Path(font).stem in script, cfg["render"], rng):
                kind = "manuscrito"  # símbolo que a fonte não tem: fica o digitado original
            fields.append({"kind": kind, "label": e["label"], "text": text, "box": e["box"]})
        s = LONG_SIDE / max(page.shape[:2])
        page = cv2.resize(page, (round(page.shape[1] * s), round(page.shape[0] * s)),
                          interpolation=cv2.INTER_AREA)
        name = f"{doc['id']}.jpg"
        cv2.imwrite(str(out / "images" / name), page, [cv2.IMWRITE_JPEG_QUALITY, 90])
        rows.append({"id": doc["id"], "image": f"pages/{NAME}/images/{name}",
                     "font": Path(font).stem, "fields": fields})
    with open(out / "pages.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    n_hw = sum(x["kind"] == "manuscrito" for r in rows for x in r["fields"])
    print(f"  {len(rows)} páginas, {n_hw} campos manuscritos, "
          f"{sum(len(r['fields']) for r in rows) - n_hw} impressos -> {out}")
    return out


def infix_distance(pattern: str, text: str) -> int:
    """Menor distância de edição entre `pattern` e qualquer trecho de `text`."""
    if not pattern:
        return 0
    if not text:
        return len(pattern)
    t = np.frombuffer(text.encode("utf-32-le"), dtype=np.uint32)
    ar = np.arange(len(t) + 1, dtype=np.int64)
    prev = np.zeros(len(t) + 1, dtype=np.int64)  # começar em qualquer ponto não custa
    for i, ch in enumerate(pattern, 1):
        best = np.minimum(prev[:-1] + (t != ord(ch)), prev[1:] + 1)
        tmp = np.concatenate([[i], best])
        prev = np.minimum.accumulate(tmp - ar) + ar  # inserções, em forma vetorizada
    return int(prev.min())


def score(cfg: dict, name: str = NAME) -> dict:
    data = resolve(cfg, "raw").parent / "pages" / name / "pages.jsonl"
    pages = {r["id"]: r for r in map(json.loads, open(data, encoding="utf-8"))}
    root = resolve(cfg, "experiments") / "paginas"
    results = {}
    for f in sorted(root.glob(f"*/{name}.jsonl")):
        tag = f.parent.name
        acc = {k: {"dist": 0, "chars": 0, "campos": 0, "exatos": 0} for k in ("manuscrito", "impresso")}
        for r in map(json.loads, open(f, encoding="utf-8")):
            pred = normalize(r["pred"])
            for fld in pages[r["id"]]["fields"]:
                d = infix_distance(fld["text"], pred)
                a = acc[fld["kind"]]
                a["dist"] += d
                a["chars"] += len(fld["text"])
                a["campos"] += 1
                a["exatos"] += d == 0
        results[tag] = {k: {"cer": a["dist"] / max(a["chars"], 1),
                            "acerto_exato": a["exatos"] / max(a["campos"], 1), "campos": a["campos"]}
                        for k, a in acc.items()}
    title = {"xfund_hw": "formulários XFUND-PT com os campos preenchidos reescritos à mão",
             "ocrsd": "certidões sintéticas do OCRSD (casamento, nascimento, óbito) preenchidas à mão"}
    lines = [f"Páginas inteiras: {title.get(name, name)}.",
             "CER = distância de cada campo ao trecho mais parecido da saída / tamanho do campo.", "",
             "| Modelo | Manuscrito CER | Manuscrito exatos | Impresso CER | Impresso exatos |",
             "|---|---|---|---|---|"]
    for tag, m in results.items():
        hw, pr = m["manuscrito"], m["impresso"]
        lines.append(f"| {tag} | {100 * hw['cer']:.1f} | {100 * hw['acerto_exato']:.1f} | "
                     f"{100 * pr['cer']:.1f} | {100 * pr['acerto_exato']:.1f} |")
    suffix = "" if name == NAME else f"_{name}"
    (root / f"comparacao{suffix}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (root / f"comparacao{suffix}.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("\n".join(lines))
    return results


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "score"])
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--set", default=NAME, help="conjunto em data/pages/ (xfund_hw, ocrsd)")
    args = ap.parse_args()
    cfg = load_config(args.config)
    build(cfg) if args.cmd == "build" else score(cfg, args.set)


if __name__ == "__main__":
    main()
