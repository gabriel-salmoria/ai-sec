"""Renderização de uma linha manuscrita sintética (tinta sobre fundo branco).

Cada palavra é desenhada inteira (preserva as ligaduras das fontes cursivas) com
deslocamento de linha de base, rotação e espaçamento aleatórios. Depois a linha
inteira recebe inclinação (cisalhamento), deformação elástica e variação de traço.
Retorna a imagem BGR e a máscara de tinta (usada no controle de qualidade).
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


def render_line(text: str, font_path: str, rc: dict, rng: np.random.Generator):
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

    # Inclinação (itálico) via cisalhamento horizontal.
    s = rng.uniform(*rc["slant"])
    h, w = canvas.shape
    M = np.float32([[1, s, -s * h / 2], [0, 1, 0]])
    canvas = cv2.warpAffine(canvas, M, (w + int(abs(s) * h), h), flags=cv2.INTER_LINEAR)

    # Deformação elástica suave (campo aleatório borrado).
    alpha = rng.uniform(*rc["elastic_alpha"])
    if alpha > 0:
        h, w = canvas.shape
        sigma = rc["elastic_sigma"]
        dx = cv2.GaussianBlur(rng.uniform(-1, 1, (h, w)).astype(np.float32), (0, 0), sigma)
        dy = cv2.GaussianBlur(rng.uniform(-1, 1, (h, w)).astype(np.float32), (0, 0), sigma)
        dx *= alpha / (np.abs(dx).max() + 1e-6)
        dy *= alpha / (np.abs(dy).max() + 1e-6)
        gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
        canvas = cv2.remap(canvas, gx + dx, gy + dy, cv2.INTER_LINEAR)

    # Espessura do traço.
    if rng.random() < rc["p_stroke_change"]:
        k = np.ones((2, 2), np.uint8)
        canvas = cv2.dilate(canvas, k) if rng.random() < 0.6 else cv2.erode(canvas, k)

    # Recorte na tinta + margem e normalização de altura.
    ys, xs = np.where(canvas > 40)
    if len(xs) == 0:
        raise ValueError(f"linha vazia após renderização: {text!r}")
    m = int(rng.integers(rc["margin"][0], rc["margin"][1] + 1))
    canvas = np.pad(canvas, m)
    canvas = canvas[ys.min():ys.max() + 2 * m + 1, xs.min():xs.max() + 2 * m + 1]
    target_h = int(rng.integers(rc["height"][0], rc["height"][1] + 1))
    scale = target_h / canvas.shape[0]
    canvas = cv2.resize(canvas, (max(1, int(canvas.shape[1] * scale)), target_h),
                        interpolation=cv2.INTER_AREA)

    # Cor da tinta sobre papel branco.
    colors = rc["ink_colors"]
    ink = np.array(colors[rng.integers(len(colors))], np.float32)
    ink = np.clip(ink + rng.normal(0, 10, 3), 0, 255)
    a = (canvas.astype(np.float32) / 255.0)[..., None]
    bgr = (255.0 * (1 - a) + ink * a).astype(np.uint8)
    return bgr, canvas, {"font_size": size, "slant": round(float(s), 3)}
