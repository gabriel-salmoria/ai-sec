"""Normalização de nomes e parsing de nomes completos em prenome/sobrenomes."""
from __future__ import annotations

import re
import unicodedata

PARTICLES = {"DA", "DE", "DO", "DAS", "DOS", "E", "DI", "DEL", "DU", "VAN", "VON", "DER"}
# Agnomes por gênero, na forma de exibição.
AGNOMES_M = ["Júnior", "Filho", "Neto", "Sobrinho"]
AGNOMES_F = ["Filha", "Neta"]
AGNOME_KEYS = {"JUNIOR", "JR", "FILHO", "FILHA", "NETO", "NETA", "SOBRINHO", "SOBRINHA"}

# Letras maiúsculas latinas (com acento) e apóstrofo, como em D'ÁVILA.
_VALID_TOKEN = re.compile(r"^[A-ZÀ-ÖØ-Ý']+$")


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def key(token: str) -> str:
    """Chave canônica: maiúsculas sem acento (formato do IBGE e da RFB)."""
    return strip_accents(token).upper()


def valid_token(token: str) -> bool:
    return bool(_VALID_TOKEN.match(token)) and len(token.strip("'")) >= 2


def display(token: str) -> str:
    """Forma de exibição em caixa de título; partículas ficam minúsculas."""
    t = token.lower()
    if t.upper() in PARTICLES:
        return t
    return "'".join(p[:1].upper() + p[1:] for p in t.split("'"))


def parse_full_name(name: str):
    """Separa um nome completo em (prenome, candidato, [(partícula, sobrenome)], agnome).

    O 1º token é prenome. Em nomes com 3+ tokens, o 2º (se não for partícula) é um
    `candidato` ambíguo: pode ser prenome composto (JOÃO PEDRO) ou sobrenome
    (MARIA SANTOS SILVA); quem decide é o léxico, comparando frequências. Partículas
    (DA, DOS...) ficam associadas ao sobrenome seguinte. Retorna None se inválido.
    """
    toks = name.strip().upper().split()
    if len(toks) < 2 or not all(_VALID_TOKEN.match(t) for t in toks):
        return None
    agnome = None
    if key(toks[-1]) in AGNOME_KEYS and len(toks) >= 3:
        agnome = toks[-1]
        toks = toks[:-1]
    first, i, candidate = toks[0], 1, None
    if len(toks) >= 3 and key(toks[1]) not in PARTICLES and valid_token(toks[1]):
        candidate, i = toks[1], 2
    surnames = []
    particle = None
    for t in toks[i:]:
        if key(t) in PARTICLES:
            particle = t
            continue
        if valid_token(t):
            surnames.append((particle, t))
        particle = None
    if not surnames:
        return None
    return first, candidate, surnames, agnome


def levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]
