"""Mãos (quem escreve) e degradação na letra e na palavra.

Uma página = uma mão e uma caneta. A mão fixa o estilo de quem escreve (fonte ou gerador,
inclinação, largura, espessura, espaçamento) e o nível de dificuldade controla quanto a
escrita se desfaz: variação letra a letra, letras que se fundem, finais de palavra que
viram traço, falhas e borrões de tinta. Tudo devolve a máscara de tinta (uint8, 0-255);
a cor entra na composição da página.
"""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from ..render import _font, _smooth_field, _stroke_width, render_line

# Parâmetros por nível. O nível 1 já é bem mais difícil que o gerador de linhas v2.
LEVELS = {
    1: dict(glyph=(0.10, 0.035, 0.11, 0.19), tremor=(0.2, 0.7), elastic=(1.0, 2.2), jitter=3, rot=1.5,
            space=(0.5, 1.4), skips=0.010, blobs=0.008, collapse=0.10, tails=0.00, smear=0.04),
    2: dict(glyph=(0.12, 0.045, 0.13, 0.24), tremor=(0.3, 0.9), elastic=(1.5, 2.8), jitter=4, rot=2.0,
            space=(0.4, 1.5), skips=0.020, blobs=0.012, collapse=0.18, tails=0.10, smear=0.07),
    3: dict(glyph=(0.14, 0.055, 0.16, 0.29), tremor=(0.4, 1.0), elastic=(2.0, 3.4), jitter=5, rot=2.8,
            space=(0.35, 1.6), skips=0.025, blobs=0.012, collapse=0.20, tails=0.15, smear=0.08),
    4: dict(glyph=(0.16, 0.065, 0.18, 0.33), tremor=(0.5, 1.2), elastic=(2.4, 3.8), jitter=6, rot=3.5,
            space=(0.3, 1.7), skips=0.035, blobs=0.016, collapse=0.25, tails=0.22, smear=0.10),
}


# ----------------------------------------------------------------------------- operações
def _disk(r: int) -> np.ndarray:
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))


def ink_skips(a: np.ndarray, p: float, rng) -> np.ndarray:
    """Falhas da caneta: pedaços do traço somem (traço interrompido)."""
    ys, xs = np.nonzero(a > 128)
    if len(xs) == 0 or p <= 0:
        return a
    h = a.shape[0]
    k = rng.binomial(len(xs), min(p * 0.02, 1.0))
    out = a.copy()
    for i in rng.choice(len(xs), size=min(k, len(xs)), replace=False):
        r = int(rng.integers(1, max(2, int(0.035 * h)) + 1))
        cv2.circle(out, (int(xs[i]), int(ys[i])), r, 0, -1)
    return out


def ink_blobs(a: np.ndarray, p: float, rng) -> np.ndarray:
    """Borrões: a tinta acumula em pontos do traço (início/fim de traço, caneta parada)."""
    ys, xs = np.nonzero(a > 128)
    if len(xs) == 0 or p <= 0:
        return a
    h = a.shape[0]
    k = rng.binomial(len(xs), min(p * 0.004, 1.0))
    out = a.copy()
    for i in rng.choice(len(xs), size=min(k, len(xs)), replace=False):
        r = int(rng.integers(1, max(2, int(0.05 * h)) + 1))
        cv2.circle(out, (int(xs[i]), int(ys[i])), r, 255, -1)
    return out


def collapse(a: np.ndarray, strength: float, rng) -> np.ndarray:
    """Letras que se fundem: trechos curtos da linha são comprimidos na horizontal
    ("rn" vira "m", "cl" vira "d"), sem mudar a altura."""
    if strength <= 0:
        return a
    h, w = a.shape
    step = max(h * 0.35, 4.0)
    dips = np.clip(_smooth_field(w, step, 1.0, rng), 0, None)
    dens = np.clip(1.0 - strength * 1.6 * dips, 0.35, 1.0)
    u_of_x = np.concatenate([[0.0], np.cumsum(dens)[:-1]]).astype(np.float32)
    out_w = max(int(u_of_x[-1]) + 1, 2)
    x_u = np.interp(np.arange(out_w, dtype=np.float32), u_of_x, np.arange(w, dtype=np.float32))
    map_x = np.repeat(x_u[None, :], h, 0).astype(np.float32)
    map_y = np.repeat(np.arange(h, dtype=np.float32)[:, None], out_w, 1)
    return cv2.remap(a, map_x, map_y, cv2.INTER_LINEAR)


def _baseline(a: np.ndarray) -> int:
    rows = (a > 128).sum(1).astype(np.float32)
    if rows.sum() == 0:
        return a.shape[0] // 2
    c = np.cumsum(rows) / rows.sum()
    return int(np.searchsorted(c, 0.8))


def sloppy_tails(a: np.ndarray, strength: float, rng) -> np.ndarray:
    """Finais de palavra que se achatam em direção à linha de base, como quem escreve rápido."""
    if strength <= 0:
        return a
    h, w = a.shape
    cols = (a > 100).sum(0) > 0
    gap = max(int(0.22 * h), 3)
    words, start, run = [], None, 0
    for x, c in enumerate(cols):
        if c:
            if start is None:
                start = x
            run = 0
        elif start is not None:
            run += 1
            if run >= gap:
                words.append((start, x - run))
                start, run = None, 0
    if start is not None:
        words.append((start, w - 1))
    base = _baseline(a)
    sy = np.ones(w, np.float32)
    for x0, x1 in words:
        if x1 - x0 < 0.8 * h or rng.random() > strength:
            continue
        frac = rng.uniform(0.25, 0.6)
        t0 = int(x1 - frac * (x1 - x0))
        floor = 1.0 - rng.uniform(0.15, 0.4) * strength
        sy[t0:x1 + 1] = np.linspace(1.0, max(floor, 0.25), x1 + 1 - t0)
    v = np.arange(h, dtype=np.float32)[:, None]
    map_y = (base + (v - base) / sy[None, :]).astype(np.float32)
    map_x = np.repeat(np.arange(w, dtype=np.float32)[None, :], h, 0)
    return cv2.remap(a, map_x, map_y, cv2.INTER_LINEAR, borderValue=0)


def smear(a: np.ndarray, p: float, rng) -> np.ndarray:
    """Traço arrastado (borrão de movimento curto)."""
    if rng.random() > p:
        return a
    k = int(rng.integers(3, 7))
    ker = np.zeros((k, k), np.float32)
    ang = rng.uniform(0, np.pi)
    c = k // 2
    cv2.line(ker, (int(c - c * np.cos(ang)), int(c - c * np.sin(ang))),
             (int(c + c * np.cos(ang)), int(c + c * np.sin(ang))), 1.0, 1)
    ker /= ker.sum()
    return np.maximum(a, cv2.filter2D(a, -1, ker))


def set_pen(a: np.ndarray, width: float) -> np.ndarray:
    """Leva o traço para a espessura de uma esferográfica (relativa ao tamanho da letra):
    engrossa fontes de traço fino e afina as grossas, que nenhuma caneta comum faz."""
    for _ in range(3):
        w = _stroke_width(a)
        if w < width * 0.8:
            a = cv2.dilate(a, _disk(max(int(round((width - w) / 2)), 1)))
        elif w > width * 1.3 and w > 2.5:
            a = cv2.erode(a, _disk(1))
        else:
            break
    return a


# Quanto da degradação cada classe de campo recebe. Números não se recuperam pelo
# contexto (um dígito ilegível é ruído no rótulo), então se desfazem pouco; campos de
# valores fechados e texto comum se recuperam pelo rótulo do campo e pelo português.
CLASS_FACTOR = {"number": 0.35, "date": 0.6, "name": 0.85, "place": 0.85, "closed": 1.0, "text": 1.0}


def degrade_ink(a: np.ndarray, level: int, rng, cls: str = "text") -> np.ndarray:
    L = LEVELS[level]
    k = CLASS_FACTOR.get(cls, 1.0)
    a = collapse(a, L["collapse"] * k * rng.uniform(0.5, 1.2), rng)
    if cls != "number":
        a = sloppy_tails(a, min(L["tails"] * k, 0.9), rng)
    a = ink_skips(a, L["skips"] * k * rng.uniform(0.3, 1.5), rng)
    a = ink_blobs(a, L["blobs"] * rng.uniform(0.3, 1.5), rng)
    return smear(a, L["smear"], rng)


# ----------------------------------------------------------------------------- mãos
class FontHand:
    """Fonte manuscrita com o estilo de quem escreve fixado para a página inteira."""

    kind = "font"

    def can(self, text: str) -> bool:
        return True

    def __init__(self, font_path: str, script: bool, base_rc: dict, level: int, rng):
        L = LEVELS[level]
        self.font_path, self.script, self.level = font_path, script, level
        rc = dict(base_rc)
        slant = float(rng.uniform(*base_rc["slant"]))
        width = float(rng.uniform(*base_rc["width_scale"]))
        if script:
            width = max(width, base_rc.get("script_min_width", 0.9))
        stroke = float(rng.uniform(*base_rc["stroke"]))
        ws = rng.uniform(*L["space"])
        rc.update(slant=[slant, slant], width_scale=[width, width], stroke=[stroke, stroke],
                  word_space=[ws * 0.8, ws * 1.25], baseline_jitter=L["jitter"], word_rotation=L["rot"],
                  tremor_alpha=list(L["tremor"]), elastic_alpha=list(L["elastic"]), elastic_sigma=4.0,
                  margin=[2, 4], font_size=[64, 76], size_drift=0.08, tilt=1.0, bow=0.03,
                  glyph=dict(base_rc["glyph"], scale=L["glyph"][0], baseline=L["glyph"][1],
                             slant=L["glyph"][2], width=L["glyph"][3]))
        self.rc = rc
        self.pen = float(rng.uniform(0.11, 0.16))  # espessura / altura do "x"
        self.desc = {"hand": "font", "font": font_path.rsplit("/", 1)[-1][:-4], "slant": round(slant, 2),
                     "width": round(width, 2), "stroke": round(stroke, 2), "pen": round(self.pen, 1)}

    def render(self, text: str, xheight: float, rng, cls: str = "text") -> np.ndarray:
        """Linha com a altura do "x" pedida (px a 300 dpi), já degradada."""
        h0 = int(max(xheight * 3.2, 24))
        rc = dict(self.rc, height=[h0, h0])
        _, a, info = render_line(text, self.font_path, rc, rng, self.script)
        f = xheight / max(info["xh_frac"] * h0, 1.0)
        if abs(f - 1) > 0.05:
            a = cv2.resize(a, (max(int(a.shape[1] * f), 1), max(int(a.shape[0] * f), 1)),
                           interpolation=cv2.INTER_AREA if f < 1 else cv2.INTER_LINEAR)
        return degrade_ink(set_pen(a, float(np.clip(xheight * self.pen, 3.2, 7.5))), self.level, rng, cls)


class TypeHand:
    """Máquina de escrever: avanço fixo, letra que sobe/desce e fita com tinta irregular."""

    kind = "type"

    def can(self, text: str) -> bool:
        return True

    def __init__(self, font_path: str, rng):
        self.font_path = font_path
        self.faint = float(rng.uniform(0.0, 0.25))
        self.desc = {"hand": "type", "font": font_path.rsplit("/", 1)[-1][:-4]}

    def render(self, text: str, xheight: float, rng, cls: str = "text") -> np.ndarray:
        size = max(int(xheight / 0.45), 8)
        font = _font(self.font_path, size)
        adv = font.getlength("M")
        asc, desc = font.getmetrics()
        w = int(adv * (len(text) + 2))
        img = Image.new("L", (max(w, 4), asc + desc + 8), 0)
        d = ImageDraw.Draw(img)
        for i, ch in enumerate(text):
            dy = int(rng.normal(0, max(size * 0.03, 0.5)))
            fill = int(255 * np.clip(1 - self.faint * rng.random() - (0.5 if rng.random() < 0.02 else 0), 0.2, 1))
            d.text((adv * (i + 1), 4 + asc + dy), ch, font=font, fill=fill, anchor="ls")
        a = np.array(img)
        ys, xs = np.nonzero(a > 40)
        if len(xs) == 0:
            return a
        return a[max(ys.min() - 2, 0):ys.max() + 3, max(xs.min() - 2, 0):xs.max() + 3]


def check_mark(size: int, rng, stroke: int) -> np.ndarray:
    """X, ✓ ou barra feitos à mão dentro de uma caixinha."""
    a = np.zeros((size, size), np.uint8)
    j = lambda: rng.uniform(-0.1, 0.1) * size
    kind = rng.choice(["x", "check", "slash"], p=[0.5, 0.3, 0.2])
    pts = {"x": [[(0.15, 0.15), (0.85, 0.85)], [(0.85, 0.15), (0.15, 0.85)]],
           "check": [[(0.15, 0.55), (0.4, 0.85), (0.9, 0.1)]],
           "slash": [[(0.2, 0.15), (0.8, 0.85)]]}[kind]
    for line in pts:
        p = np.array([[x * size + j(), y * size + j()] for x, y in line], np.int32)
        cv2.polylines(a, [p], False, 255, max(stroke, 1), cv2.LINE_AA)
    return a


class NeuralHand:
    """Escrita de um gerador neural (Graves/sjvasquez, VATr++, Emuru), já renderizada em lote
    por `scripts/hw/render_<gerador>.py` (cada um no seu ambiente). `cache` mapeia o texto
    para o PNG gerado com o estilo da página; textos fora do alfabeto do gerador não chegam
    aqui (vão para a máquina de escrever)."""

    def __init__(self, kind: str, cache: dict[str, str], level: int, rng, style=None, bias=None):
        self.kind, self.cache, self.level = kind, cache, level
        self.pen = float(rng.uniform(0.11, 0.16))
        self.desc = {"hand": kind, "style": style, "bias": bias, "pen": round(self.pen, 1)}

    def can(self, text: str) -> bool:
        return text in self.cache

    def render(self, text: str, xheight: float, rng, cls: str = "text") -> np.ndarray:
        path = self.cache.get(text)
        if path is None:
            raise KeyError(f"sem renderização neural para {text!r}")
        img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if img.ndim == 3 and img.shape[2] == 4:
            a = img[..., 3]
        else:
            g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
            a = 255 - g
        a = np.where(a > 25, a, 0).astype(np.float32)
        if a.max() > 0:  # tinta cinza-clara do gerador -> tinta de caneta
            a = np.clip(a / max(np.percentile(a[a > 0], 90), 1.0), 0, 1) * 255
        a = a.astype(np.uint8)
        ys, xs = np.nonzero(a)
        if len(xs) == 0:
            raise ValueError(f"renderização vazia para {text!r}")
        a = np.pad(a[ys.min():ys.max() + 1, xs.min():xs.max() + 1], 3)
        # altura do "x": faixa central que concentra a tinta (sem hastes e pernas)
        rows = (a > 60).sum(1).astype(np.float32)
        c = np.cumsum(rows) / max(rows.sum(), 1)
        core = max(np.searchsorted(c, 0.8) - np.searchsorted(c, 0.2), 2)
        f = xheight / (core / 0.75)
        a = cv2.resize(a, (max(int(a.shape[1] * f), 1), max(int(a.shape[0] * f), 1)),
                       interpolation=cv2.INTER_AREA if f < 1 else cv2.INTER_LINEAR)
        return degrade_ink(set_pen(a, float(np.clip(xheight * self.pen, 3.2, 7.5))), self.level, rng, cls)
