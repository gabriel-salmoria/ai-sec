"""Degradação com Augraphy para imitar documento escaneado/fotografado.

O nível (leve/médio/forte) é sorteado por amostra e escala a probabilidade de cada
augmentation. O Augraphy usa os geradores globais (random, numpy, cv2), então eles
são re-semeados a cada amostra para que a imagem seja reproduzível pela seed.
"""
from __future__ import annotations

import random

import cv2
import numpy as np
from augraphy import (AugraphyPipeline, BadPhotoCopy, BrightnessTexturize, ColorPaper,
                      DirtyDrum, Gamma, InkBleed, Jpeg, LightingGradient, LowInkRandomLines,
                      NoiseTexturize, SubtleNoise)


def build_pipeline(scale: float) -> AugraphyPipeline:
    def p(x: float) -> float:
        return min(1.0, x * scale)

    ink = [
        InkBleed(intensity_range=(0.2, 0.5), kernel_size=(3, 3), severity=(0.2, 0.4), p=p(0.4)),
        LowInkRandomLines(count_range=(2, 6), noise_probability=0.05, p=p(0.25)),
    ]
    paper = [
        ColorPaper(hue_range=(20, 45), saturation_range=(5, 35), p=p(0.5)),
        NoiseTexturize(sigma_range=(2, 6), turbulence_range=(2, 4), p=p(0.5)),
        BrightnessTexturize(texturize_range=(0.9, 0.99), deviation=0.05, p=p(0.4)),
    ]
    post = [
        SubtleNoise(subtle_range=8, p=p(0.5)),
        Gamma(gamma_range=(0.7, 1.3), p=p(0.3)),
        LightingGradient(max_brightness=255, min_brightness=120, mode="gaussian",
                         transparency=0.6, p=p(0.2)),
        BadPhotoCopy(noise_type=-1, noise_iteration=(1, 1), noise_sparsity=(0.6, 0.9),
                     noise_concentration=(0.05, 0.2), p=p(0.12)),
        DirtyDrum(line_width_range=(1, 2), noise_intensity=0.2, p=p(0.08)),
        Jpeg(quality_range=(40, 90), p=p(0.5)),
    ]
    return AugraphyPipeline(ink_phase=ink, paper_phase=paper, post_phase=post)


class Degrader:
    def __init__(self, dc: dict):
        self.dc = dc
        self.levels = list(dc["levels"])
        w = np.array(list(dc["levels"].values()), dtype=float)
        self.level_p = w / w.sum()
        self.pipelines = {lv: build_pipeline(dc["scale"][lv]) for lv in self.levels}

    def __call__(self, bgr: np.ndarray, seed: int, rng: np.random.Generator):
        level = self.levels[rng.choice(len(self.levels), p=self.level_p)]
        random.seed(seed)
        np.random.seed(seed % 2**32)
        cv2.setRNGSeed(seed % 2**31)
        out = self.pipelines[level](bgr)
        if out.ndim == 2:
            out = cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)
        return out, level


def ink_contrast(img: np.ndarray, ink_mask: np.ndarray) -> float:
    """Diferença média de cinza entre fundo e tinta (proxy barato de legibilidade)."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    if gray.shape != ink_mask.shape:
        ink_mask = cv2.resize(ink_mask, (gray.shape[1], gray.shape[0]))
    ink = ink_mask > 160
    bg = cv2.dilate(ink_mask, np.ones((5, 5), np.uint8)) < 10
    if ink.sum() == 0 or bg.sum() == 0:
        return 0.0
    return float(gray[bg].mean() - gray[ink].mean())
