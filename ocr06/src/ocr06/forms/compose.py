"""Composição da página: escreve os campos do registro no modelo em branco e degrada o papel.

Saída de `make_page`: imagem BGR já no tamanho que o modelo vê (lado maior 2048 px) e a
lista de campos escritos, com o texto (o que um transcritor humano escreveria: o valor
pretendido, em português), a classe do campo, quem escreveu e a caixa da tinta na imagem
final (px e normalizada 0-1000, como o Chandra descreve blocos).
"""
from __future__ import annotations

import random

import cv2
import numpy as np
from augraphy import (AugraphyPipeline, BadPhotoCopy, BrightnessTexturize, ColorPaper, 
                      Gamma, InkBleed, Jpeg, LightingGradient, LowInkRandomLines,
                      NoiseTexturize, ShadowCast, SubtleNoise)

from ..degrade import ink_contrast
from .hands import check_mark
from .records import field_class, mapping_fields

MAX_SIDE = 2048
MIN_CONTRAST = 45  # diferença média de cinza entre fundo e tinta (0-255)
PEN_INKS = [(120, 40, 15), (90, 30, 10), (35, 30, 30), (100, 45, 25), (70, 35, 20)]  # BGR, esferográfica
TYPE_INK = (35, 35, 35)


# ----------------------------------------------------------------------------- papel/scan
def paper_pipeline(level: int) -> AugraphyPipeline:
    s = {1: 0.35, 2: 0.55, 3: 0.72, 4: 0.85}[level]
    p = lambda x: min(1.0, x * s)
    ink = [InkBleed(intensity_range=(0.2, 0.5), kernel_size=(3, 3), severity=(0.2, 0.5), p=p(0.5)),
           LowInkRandomLines(count_range=(3, 10), noise_probability=0.08, p=p(0.3))]
    paper = [ColorPaper(hue_range=(18, 40), saturation_range=(10, 45), p=p(0.6)),
             NoiseTexturize(sigma_range=(2, 5), turbulence_range=(2, 4), p=p(0.5)),
             BrightnessTexturize(texturize_range=(0.85, 0.98), deviation=0.06, p=p(0.5))]
    post = [SubtleNoise(subtle_range=10, p=p(0.6)), Gamma(gamma_range=(0.7, 1.3), p=p(0.4)),
            LightingGradient(max_brightness=255, min_brightness=110, mode="gaussian",
                             transparency=0.55, p=p(0.3))]
    if level >= 2:
        post.append(BadPhotoCopy(noise_type=-1, noise_iteration=(1, 1), noise_sparsity=(0.8, 0.95),
                                 noise_concentration=(0.02, 0.08), p=p(0.1)))
    if level >= 3:
        post.append(ShadowCast(shadow_opacity_range=(0.15, 0.35), p=p(0.12)))
    return AugraphyPipeline(ink_phase=ink, paper_phase=paper, post_phase=post)


_PIPES: dict[int, AugraphyPipeline] = {}


def degrade_page(img: np.ndarray, level: int, seed: int, rng) -> tuple[np.ndarray, np.ndarray]:
    """Papel, cópia e scan. Devolve a imagem e a matriz afim aplicada às coordenadas."""
    if level not in _PIPES:
        _PIPES[level] = paper_pipeline(level)
    random.seed(seed)
    np.random.seed(seed % 2**32)
    cv2.setRNGSeed(seed % 2**31)
    out = _PIPES[level](img)
    if out.ndim == 2:
        out = cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)
    h, w = out.shape[:2]
    # Manchas leves de papel velho (amarelado, em poucas regiões), não borrões cinza.
    if rng.random() < {1: 0.1, 2: 0.25, 3: 0.4, 4: 0.55}[level]:
        m = np.zeros((h, w), np.float32)
        for _ in range(int(rng.integers(1, 4))):
            c = (int(rng.integers(w)), int(rng.integers(h)))
            ax = (int(rng.uniform(0.05, 0.2) * w), int(rng.uniform(0.04, 0.15) * h))
            cv2.ellipse(m, c, ax, float(rng.uniform(0, 180)), 0, 360, 1.0, -1)
        m = cv2.GaussianBlur(m, (0, 0), 0.03 * w) * rng.uniform(0.08, 0.22)
        tint = np.array([60, 25, 0], np.float32)  # tira azul/verde = amarelado (BGR)
        out = (out.astype(np.float32) - m[..., None] * tint).clip(0, 255).astype(np.uint8)
    # Resolução baixa (scanner/microfilme) nos níveis altos.
    if rng.random() < {1: 0.0, 2: 0.05, 3: 0.1, 4: 0.15}[level]:
        f = rng.uniform(0.75, 0.85)
        small = cv2.resize(out, (int(w * f), int(h * f)), interpolation=cv2.INTER_AREA)
        out = cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)
    # Página levemente torta no scanner.
    ang = rng.uniform(-1, 1) * {1: 0.3, 2: 0.6, 3: 1.0, 4: 1.8}[level]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), ang, 1.0)
    out = cv2.warpAffine(out, M, (w, h), borderMode=cv2.BORDER_REPLICATE)
    q = int(rng.integers(*{1: (88, 96), 2: (80, 94), 3: (72, 90), 4: (62, 85)}[level]))
    out = cv2.imdecode(cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, q])[1], cv2.IMREAD_COLOR)
    return out, M


# ----------------------------------------------------------------------------- escrita
def _paste(layer: np.ndarray, a: np.ndarray, x: int, y: int) -> tuple[int, int, int, int] | None:
    H, W = layer.shape
    h, w = a.shape
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
    if x1 <= x0 or y1 <= y0:
        return None
    sub = a[y0 - y:y1 - y, x0 - x:x1 - x]
    np.maximum(layer[y0:y1, x0:x1], sub, out=layer[y0:y1, x0:x1])
    ys, xs = np.nonzero(sub > 60)
    if len(xs) == 0:
        return None
    return x0 + int(xs.min()), y0 + int(ys.min()), x0 + int(xs.max()) + 1, y0 + int(ys.max()) + 1


def _union(boxes):
    boxes = [b for b in boxes if b]
    if not boxes:
        return None
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def _taper(a: np.ndarray, target: float, rng) -> np.ndarray:
    """Como quem percebe que não vai caber: a letra encolhe aos poucos a partir do meio da
    linha (largura e altura juntas, em torno da linha de base)."""
    h, w = a.shape
    t0 = rng.uniform(0.45, 0.7)
    f_end = 2 * (target - t0 * w) / (w * (1 - t0)) - 1
    if f_end < 0.5:
        return a
    x = np.arange(w, dtype=np.float32)
    k = np.where(x < t0 * w, 1.0, 1.0 + (f_end - 1.0) * (x - t0 * w) / (w * (1 - t0))).astype(np.float32)
    u_of_x = np.concatenate([[0.0], np.cumsum(k)[:-1]]).astype(np.float32)
    out_w = max(int(u_of_x[-1]) + 1, 2)
    x_u = np.interp(np.arange(out_w, dtype=np.float32), u_of_x, x)
    k_u = np.interp(x_u, x, k)
    rows = (a > 100).sum(1)
    base = int(np.searchsorted(np.cumsum(rows) / max(rows.sum(), 1), 0.8))
    v = np.arange(h, dtype=np.float32)[:, None]
    map_y = (base + (v - base) / k_u[None, :]).astype(np.float32)
    map_x = np.repeat(x_u[None, :].astype(np.float32), h, 0)
    return cv2.remap(a, map_x, map_y, cv2.INTER_LINEAR, borderValue=0)


def _fit_line(a: np.ndarray, bw: int, level: int, rng, cls: str = "text") -> np.ndarray:
    """Linha mais larga que a caixa. Pode passar um pouco da borda (até ~8%), mas quem escreve
    percebe e corrige: aperta a letra um pouco e vai diminuindo o tamanho no fim da linha."""
    target = bw * rng.uniform(1.0, 1.08)
    h, w = a.shape
    if w <= target:
        return a
    sx = max(target / w, 0.85)  # um pouco mais apertada
    a = cv2.resize(a, (max(int(w * sx), 1), h), interpolation=cv2.INTER_AREA)
    if a.shape[1] > target:
        a = _taper(a, target, rng)  # e encolhendo no fim
    if a.shape[1] > target * 1.02:  # texto demais para a caixa: letra menor desde o início
        f = target / a.shape[1]
        a = cv2.resize(a, (max(int(a.shape[1] * f), 1), max(int(a.shape[0] * f), 1)), interpolation=cv2.INTER_AREA)
    return a


def write_text(layer, hand, text, box, level, rng, cls="text"):
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    # altura do "x" ~1/3 da caixa, mas nunca menor que a letra de quem escreve à mão
    # (~2 mm = 20 px a 300 dpi): em caixa baixa, a letra passa um pouco da borda.
    xh = float(np.clip(bh * rng.uniform(0.28, 0.40), 20, 34))
    line_h = xh * 3.0
    if bh < 1.9 * line_h:  # uma linha
        a = _fit_line(hand.render(text, xh, rng, cls), bw, level, rng, cls)
        x = x0 + int(rng.uniform(0.0, 0.06) * bw)
        y = int((y0 + y1) / 2 + rng.uniform(-0.15, 0.08) * bh - a.shape[0] / 2)
        return _paste(layer, a, x, y)
    # várias linhas: mede a linha inteira e quebra em n linhas equilibradas
    xh = float(rng.uniform(20, 30))
    line_h = xh * 3.0
    full = hand.render(text, xh, rng, cls)
    n_max = max(int(bh // (line_h * 0.95)), 1)
    n = int(np.clip(np.ceil(full.shape[1] / (bw * 0.97)), 1, n_max))
    words, lines = text.split(), []
    target = len(text) / n
    cur = ""
    for wd in words:
        if cur and len(cur) + 1 + len(wd) > target * 1.08 and len(lines) < n - 1:
            lines.append(cur)
            cur = wd
        else:
            cur = f"{cur} {wd}".strip()
    lines.append(cur)
    boxes, y = [], y0 + int(rng.uniform(0.0, 0.08) * bh)
    for ln in lines:
        a = _fit_line(hand.render(ln, xh, rng, cls), bw, level, rng, cls)
        boxes.append(_paste(layer, a, x0 + int(rng.uniform(0.0, 0.04) * bw), y))
        y += int(line_h * rng.uniform(0.85, 1.05))
    return _union(boxes)


def write_cells(layer, hand, elements, level, rng):
    boxes, chars = [], []
    for e in elements:
        ch = e.get("value") or ""
        if not ch:
            continue
        x0, y0, x1, y1 = e["bbox"]
        bw, bh = x1 - x0, y1 - y0
        a = hand.render(ch, max(bh * rng.uniform(0.38, 0.58), 10), rng, "number")
        if a.shape[1] > bw * 1.3:
            f = bw * 1.2 / a.shape[1]
            a = cv2.resize(a, (max(int(a.shape[1] * f), 1), max(int(a.shape[0] * f), 1)))
        x = int(x0 + bw / 2 - a.shape[1] / 2 + rng.uniform(-0.12, 0.12) * bw)
        y = int(y0 + bh / 2 - a.shape[0] / 2 + rng.uniform(-0.12, 0.12) * bh)
        boxes.append(_paste(layer, a, x, y))
        chars.append(ch)
    return _union(boxes), "".join(chars)


def write_checks(layer, elements, stroke, rng):
    boxes, labels = [], []
    for e in elements:
        if not e.get("checked"):
            continue
        x0, y0, x1, y1 = e["bbox"]
        s = int(max(x1 - x0, y1 - y0) * rng.uniform(0.9, 1.4))
        a = check_mark(s, rng, stroke)
        boxes.append(_paste(layer, a, int((x0 + x1) / 2 - s / 2 + rng.uniform(-4, 4)),
                            int((y0 + y1) / 2 - s / 2 + rng.uniform(-4, 4))))
        labels.append(e.get("label", ""))
    return _union(boxes), "; ".join(labels)


# ----------------------------------------------------------------------------- página
def make_page(template_png: str, template: str, rec: dict, hand, typer, level: int, seed: int):
    rng = np.random.default_rng(seed)
    page = cv2.imread(template_png, cv2.IMREAD_COLOR)
    H, W = page.shape[:2]
    pen, typed = np.zeros((H, W), np.uint8), np.zeros((H, W), np.uint8)
    pen_ink = PEN_INKS[int(rng.integers(len(PEN_INKS)))]
    stroke = int(rng.integers(3, 7))
    mf = mapping_fields(template)
    fields = []
    for f in rec["fields"]:
        if f.get("blank") and not any(e.get("checked") for e in f.get("elements", [])):
            continue
        dt = mf.get(f["field_id"], {}).get("data_type")
        cls = field_class(dt, f["value"])
        els = f.get("elements") or []
        if els and any("index" in e for e in els):
            if not all(hand.can(e["value"]) for e in els if e.get("value")):
                continue  # fora do alfabeto do gerador: o campo fica em branco
            box, text = write_cells(pen, hand, els, level, rng)
            who = hand.kind
        elif els and any("checked" in e for e in els):
            box, text = write_checks(pen, els, stroke, rng)
            who, cls = "mark", "closed"
        else:
            text = " ".join(f["value"].split())
            if not hand.can(text):
                continue  # texto com acento/ç numa página de mão neural: o campo fica em branco
            box = write_text(pen, hand, text, f["bbox"], level, rng, cls)
            who = hand.kind
        if box and text:
            fields.append({"field_id": f["field_id"], "text": text, "cls": cls, "hand": who, "box_full": box})
    # Tinta de esferográfica no papel: grão (a tinta falha e acumula), borda levemente
    # espalhada e mistura multiplicativa com o papel/impressão por baixo, em vez de uma
    # camada de cor chapada colada por cima.
    a = pen.astype(np.float32) / 255.0
    gh, gw = max(H // 24, 2), max(W // 24, 2)
    grain = cv2.resize(rng.uniform(0.82, 1.0, (gh, gw)).astype(np.float32), (W, H), interpolation=cv2.INTER_CUBIC)
    fine = rng.uniform(0.9, 1.0, (H, W)).astype(np.float32)
    a = cv2.GaussianBlur(a * grain * fine, (0, 0), rng.uniform(0.4, 0.7))
    if (a > 0.1).any():  # o miolo do traço volta a ficar escuro (caneta, não lápis)
        a = a / max(float(np.percentile(a[a > 0.1], 85)), 0.3) * rng.uniform(0.93, 1.0)
    a = np.clip(a, 0, 1)[..., None]
    ink = np.array(pen_ink, np.float32) / 255.0
    out = page.astype(np.float32) * (1 - a + a * ink)
    out = out.clip(0, 255).astype(np.uint8)
    # tamanho que o modelo vê
    f = MAX_SIDE / max(H, W)
    out = cv2.resize(out, (int(W * f), int(H * f)), interpolation=cv2.INTER_AREA)
    # Passada de scanner em tudo (impresso e tinta juntos): cor mais apagada, foco levemente mole.
    hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[..., 1] *= rng.uniform(0.7, 0.92)
    out = cv2.cvtColor(hsv.clip(0, 255).astype(np.uint8), cv2.COLOR_HSV2BGR)
    out = cv2.GaussianBlur(out, (0, 0), rng.uniform(0.35, 0.75))
    ink = cv2.resize(pen, (out.shape[1], out.shape[0]), interpolation=cv2.INTER_AREA)
    clean = out
    # O papel não pode apagar a tinta: se o contraste tinta/fundo cair demais (luz estourada,
    # cópia clara), refaz o papel com outra semente e, no fim, com um nível abaixo.
    for attempt in range(4):
        lv = level if attempt < 3 else max(level - 1, 1)
        out, M = degrade_page(clean, lv, seed + 7919 * attempt, rng)
        mask = cv2.warpAffine(ink, M, (out.shape[1], out.shape[0]))
        if ink_contrast(out, mask) >= MIN_CONTRAST:
            break
    h, w = out.shape[:2]
    for fl in fields:
        x0, y0, x1, y1 = (v * f for v in fl.pop("box_full"))
        pts = np.array([[x0, y0], [x1, y0], [x0, y1], [x1, y1]], np.float32)
        pts = cv2.transform(pts[None], M)[0]
        bx = [int(pts[:, 0].min()), int(pts[:, 1].min()), int(pts[:, 0].max()), int(pts[:, 1].max())]
        fl["box"] = bx
        fl["bbox_1000"] = [round(1000 * bx[0] / w), round(1000 * bx[1] / h),
                           round(1000 * bx[2] / w), round(1000 * bx[3] / h)]
    return out, fields, {"pen_ink": pen_ink, "size": [w, h]}
