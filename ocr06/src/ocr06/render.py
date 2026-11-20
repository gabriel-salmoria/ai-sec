"""Renderização de uma linha manuscrita sintética (tinta sobre fundo branco).

Cada palavra é desenhada inteira (preserva as ligaduras das fontes cursivas) com
deslocamento de linha de base, rotação e espaçamento aleatórios. Depois a linha passa
por uma deformação que imita a variação humana em dois níveis:
  - estilo de quem escreve (um sorteio por linha): inclinação, letra estreita ou larga,
    traço fino ou grosso, pressão variando, letra que cresce ou encolhe ao longo da
    linha, linha que sobe/desce ou faz curva;
  - variação letra a letra: campos suaves ao longo da linha (~1 nó por letra) mudam a
    altura, a largura, a inclinação e a posição de cada letra, então a mesma letra
    nunca sai igual duas vezes.
Por fim, tremor fino e ondulação elástica. Retorna a imagem BGR e a máscara de tinta
(usada no controle de qualidade).
"""
from __future__ import annotations

from functools import lru_cache

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


@lru_cache(maxsize=512)
def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def _render_word(word: str, font: ImageFont.FreeTypeFont) -> tuple[np.ndarray, int]:
    """Desenha uma palavra; devolve (máscara, y da linha de base na máscara)."""
    ascent, descent = font.getmetrics()
    pad = font.size // 2
    width = int(font.getlength(word)) + 2 * pad
    img = Image.new("L", (max(width, 1), ascent + descent + 2 * pad), 0)
    ImageDraw.Draw(img).text((pad, pad + ascent), word, font=font, fill=255, anchor="ls")
    return np.array(img), pad + ascent


def _smooth_field(n: int, step: float, sd: float, rng: np.random.Generator) -> np.ndarray:
    """Ruído suave ao longo de x: um valor aleatório a cada `step` px, interpolado e
    suavizado. Com `step` ~ largura de uma letra, cada letra recebe um valor próprio."""
    if sd <= 0 or n < 2:
        return np.zeros(n, np.float32)
    k = int(n / step) + 3
    knots = rng.normal(0.0, sd, k)
    field = np.interp(np.arange(n), (np.arange(k) - 1) * step, knots).astype(np.float32)
    return cv2.GaussianBlur(field[None, :], (0, 0), max(step / 3, 1.0))[0]


def _human_warp(canvas: np.ndarray, baseline: int, size: int, rc: dict,
                rng: np.random.Generator, script: bool) -> tuple[np.ndarray, dict]:
    """Aplica o estilo da linha e a variação letra a letra num único remapeamento."""
    g = rc["glyph"]
    step = g["spacing"] * size
    slant = rng.uniform(*rc["slant"])
    sx = rng.uniform(*rc["width_scale"])
    if script:  # cursivas já são estreitas; apertar mais deixa a linha ilegível
        sx = max(sx, rc.get("script_min_width", 0.9))
    drift = rng.uniform(-rc["size_drift"], rc["size_drift"])
    tilt = np.tan(np.radians(rng.uniform(-rc["tilt"], rc["tilt"])))
    bow = rng.uniform(-rc["bow"], rc["bow"]) * size

    # Margem para o que a inclinação, a curva e as variações empurram para fora.
    h0, w0 = canvas.shape
    pad_y = int(abs(tilt) * w0 / 2 + abs(bow) + 4 * g["baseline"] * size + 0.4 * size) + 2
    pad_x = int((abs(slant) + 4 * g["slant"]) * (h0 + 2 * pad_y)) + 2
    canvas = np.pad(canvas, ((pad_y, pad_y), (pad_x, pad_x)))
    baseline += pad_y
    h, w = canvas.shape

    x = np.arange(w, dtype=np.float32)
    t = (x - pad_x) / max(w0 - 1, 1)                     # 0..1 ao longo do texto
    sy = 1.0 + drift * (2 * t - 1) + _smooth_field(w, step, g["scale"], rng)
    sy = np.clip(sy, 0.6, 1.5)
    dy = (_smooth_field(w, step, g["baseline"] * size, rng)
          + tilt * (x - w / 2) + bow * ((2 * t - 1) ** 2 - 1 / 3))
    sh = slant + _smooth_field(w, step, g["slant"], rng)
    dens = np.clip(1.0 + _smooth_field(w, step, g["width"], rng), 0.5, 1.6) * sx

    # x de origem -> u de saída (monotônico); inverte por interpolação.
    u_of_x = np.concatenate([[0.0], np.cumsum(dens)[:-1]]).astype(np.float32)
    out_w = int(u_of_x[-1]) + 1
    u = np.arange(out_w, dtype=np.float32)
    x_u = np.interp(u, u_of_x, x).astype(np.float32)
    sy_u, dy_u, sh_u = (np.interp(x_u, x, f).astype(np.float32) for f in (sy, dy, sh))

    v = np.arange(h, dtype=np.float32)[:, None]
    map_y = baseline + (v - baseline - dy_u[None, :]) / sy_u[None, :]
    map_x = x_u[None, :] + sh_u[None, :] * (map_y - baseline)
    out = cv2.remap(canvas, map_x.astype(np.float32), map_y.astype(np.float32),
                    cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    return out, {"slant": round(float(slant), 3), "width_scale": round(float(sx), 3)}


def _elastic(canvas: np.ndarray, alpha: float, sigma: float,
             rng: np.random.Generator) -> np.ndarray:
    """Deslocamento aleatório suave (sigma grande = ondulação; pequeno = tremor)."""
    if alpha <= 0:
        return canvas
    h, w = canvas.shape
    dx = cv2.GaussianBlur(rng.uniform(-1, 1, (h, w)).astype(np.float32), (0, 0), sigma)
    dy = cv2.GaussianBlur(rng.uniform(-1, 1, (h, w)).astype(np.float32), (0, 0), sigma)
    dx *= alpha / (np.abs(dx).max() + 1e-6)
    dy *= alpha / (np.abs(dy).max() + 1e-6)
    gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    return cv2.remap(canvas, gx + dx, gy + dy, cv2.INTER_LINEAR)


def _stroke_width(canvas: np.ndarray) -> float:
    """Espessura média do traço em px (área da tinta / metade do contorno)."""
    ink = (canvas > 127).astype(np.uint8)
    area = int(ink.sum())
    edge = area - int(cv2.erode(ink, np.ones((3, 3), np.uint8)).sum())
    return 2.0 * area / max(edge, 1)


def _stroke(canvas: np.ndarray, size: int, rc: dict, rng: np.random.Generator):
    """Traço fino ou grosso (por linha) e pressão variando ao longo da linha."""
    s = rng.uniform(*rc["stroke"]) * size / 48
    r = int(round(s))
    width = _stroke_width(canvas)
    if r < 0 and width >= rc.get("min_stroke_to_thin", 5.0):
        canvas = cv2.erode(canvas, np.ones((2, 2), np.uint8))
    elif r > 0 and width <= rc.get("max_stroke_to_thicken", 8.0):  # marcador grosso empasta
        canvas = cv2.dilate(canvas, cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                                              (2 * r + 1, 2 * r + 1)))
    if rng.random() < rc["p_pressure"]:
        heavy = cv2.dilate(canvas, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
        m = _smooth_field(canvas.shape[1], 1.5 * size, 1.0, rng)
        m = np.clip(0.5 + m, 0, 1)[None, :]
        canvas = (canvas * (1 - m) + heavy * m).astype(np.uint8)
    return canvas, round(float(s), 2)


def render_line(text: str, font_path: str, rc: dict, rng: np.random.Generator,
                script: bool = False):
    size = int(rng.integers(rc["font_size"][0], rc["font_size"][1] + 1))
    font = _font(font_path, size)
    space = font.getlength(" ") or size * 0.3

    words = [_render_word(w, font) for w in text.split(" ")]
    jitter = rc["baseline_jitter"]
    gaps = [int(space * rng.uniform(*rc["word_space"])) for _ in words]
    width = sum(m.shape[1] for m, _ in words) + sum(gaps) + 4 * size
    height = max(m.shape[0] for m, _ in words) + 4 * jitter + 2 * size
    canvas = np.zeros((height, width), np.uint8)
    baseline = height // 2 + size // 3
    x = size
    for (mask, base), gap in zip(words, gaps):
        angle = rng.uniform(-rc["word_rotation"], rc["word_rotation"])
        h, w = mask.shape
        M = cv2.getRotationMatrix2D((w / 2, base), angle, 1.0)
        mask = cv2.warpAffine(mask, M, (w, h), flags=cv2.INTER_LINEAR)
        y = baseline - base + int(rng.integers(-jitter, jitter + 1))
        y0, y1 = max(y, 0), min(y + h, height)
        region = canvas[y0:y1, x:x + w]
        np.maximum(region, mask[y0 - y:y1 - y, :region.shape[1]], out=region)
        x += w - font.size + gap  # desconta o padding da palavra

    canvas, style = _human_warp(canvas, baseline, size, rc, rng, script)
    canvas = _elastic(canvas, rng.uniform(*rc["tremor_alpha"]), rc["tremor_sigma"], rng)
    canvas = _elastic(canvas, rng.uniform(*rc["elastic_alpha"]), rc["elastic_sigma"], rng)
    canvas, stroke = _stroke(canvas, size, rc, rng)

    # Recorte na tinta + margem e normalização de altura.
    ys, xs = np.where(canvas > 40)
    if len(xs) == 0:
        raise ValueError(f"linha vazia após renderização: {text!r}")
    m = int(rng.integers(rc["margin"][0], rc["margin"][1] + 1))
    canvas = np.pad(canvas, m)
    canvas = canvas[ys.min():ys.max() + 2 * m + 1, xs.min():xs.max() + 2 * m + 1]
    xb = font.getbbox("x")
    xh_frac = (xb[3] - xb[1]) / canvas.shape[0]  # altura do "x" / altura da linha
    target_h = int(rng.integers(rc["height"][0], rc["height"][1] + 1))
    scale = target_h / canvas.shape[0]
    canvas = cv2.resize(canvas, (max(1, int(canvas.shape[1] * scale)), target_h),
                        interpolation=cv2.INTER_AREA)

    # Cor da tinta sobre papel branco.
    colors = rc["ink_colors"]
    ink = np.array(colors[rng.integers(len(colors))], np.float32)
    ink = np.clip(ink + rng.normal(0, rc.get("ink_color_jitter", 10), 3), 0, 255)
    a = (canvas.astype(np.float32) / 255.0)[..., None]
    bgr = (255.0 * (1 - a) + ink * a).astype(np.uint8)
    return bgr, canvas, {"font_size": size, "stroke": stroke, "xh_frac": round(xh_frac, 3),
                         **style}
