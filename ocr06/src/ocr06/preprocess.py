"""Normalização de altura das linhas antes de entrarem no modelo (treino e inferência).

As linhas do BRESSAY têm altura mediana de 20 px e as sintéticas de 48 a 112 px. O
encoder do Chandra junta a imagem em blocos de 32 px (patch 16 com fusão 2x2), então
sem normalizar uma linha real vira menos de um bloco de altura e uma sintética vira 2 a 4.
Aqui toda linha é redimensionada para a mesma altura (`preprocess.line_height`),
mantendo a proporção e limitando a largura. Só usa Pillow, porque roda tanto no
ambiente de treino quanto no do vLLM.
"""
from __future__ import annotations

import math

from PIL import Image

PATCH = 32  # lado do bloco visual depois da fusão 2x2 (Qwen3.5 / Chandra)


def target_size(w: int, h: int, cfg: dict) -> tuple[int, int]:
    pc = cfg.get("preprocess", {})
    th = pc.get("line_height")
    if not th:
        return w, h
    nw = max(1, round(w * th / h))
    max_w = pc.get("max_width")
    if max_w and nw > max_w:  # linha muito longa: limita a largura e reduz a altura junto
        return max_w, max(1, round(h * max_w / w))
    return nw, th


def normalize_line(img: Image.Image, cfg: dict) -> Image.Image:
    """Redimensiona para a altura alvo. Sem `preprocess.line_height`, devolve a imagem igual."""
    size = target_size(img.width, img.height, cfg)
    if size == img.size:
        return img
    return img.resize(size, Image.Resampling.BICUBIC)


def patch_grid(w: int, h: int) -> tuple[int, int]:
    """Número aproximado de blocos visuais (linhas, colunas). O processador do modelo
    arredonda os lados para múltiplos de 32, com no mínimo um bloco."""
    return max(1, round(h / PATCH)), max(1, round(w / PATCH))


def load_line(path, cfg: dict) -> Image.Image:
    return normalize_line(Image.open(path).convert("RGB"), cfg)


def load_page(path, max_side: int = 2048) -> Image.Image:
    """Página inteira: só reduz até o lado maior caber em `max_side` (sem a normalização de
    altura das linhas). Mesmo redimensionamento de model/pages_infer.py, para o modelo ver
    a página no treino na mesma escala da inferência."""
    im = Image.open(path).convert("RGB")
    f = max_side / max(im.size)
    if f < 1:
        im = im.resize((round(im.width * f), round(im.height * f)), Image.LANCZOS)
    return im


def max_chars(w: int, h: int, cfg: dict) -> int:
    """Limite superior de caracteres que cabem numa linha de largura w e altura h.
    Usado para limitar os tokens gerados (um token tem pelo menos um caractere na
    maioria dos casos, então o limite em caracteres também vale para tokens)."""
    gc = cfg.get("guard", {})
    k = gc.get("chars_per_height", 10.0)
    return max(gc.get("min_chars", 16), math.ceil(k * w / h))
