"""Amostragem de nomes, cidades e linhas de texto.

Os nomes vêm do vocabulário selecionado em `vocab.py` (prioridade pela frequência
real; comuns em todos os splits, parte dos raros reservada para validação/teste).
Dentro de cada split o sorteio é estratificado: a massa de comuns e raros segue a
curva suavizada q ∝ p^alpha do vocabulário inteiro. Uma fração opcional
`p_invented` vem de nomes inventados (sem população; 0 por padrão).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .common import read_csv, read_json
from .text import AGNOMES_F, AGNOMES_M
from .vocab import bucket_masses, load_rows, stratified_q


@dataclass
class Token:
    text: str
    type: str          # prenome | sobrenome | particula | agnome | cidade | uf | contexto
    bucket: str | None  # comum | raro | inventado | None
    key: str | None


class Pool:
    """Sorteio por probabilidade fixa via soma cumulativa + busca binária."""

    def __init__(self, rows: list[dict], q: np.ndarray | None = None):
        self.rows = rows
        q = np.ones(len(rows)) if q is None else np.asarray(q, dtype=float)
        self.q = q / q.sum() if len(rows) else q
        self.cum = np.cumsum(self.q)

    def __len__(self):
        return len(self.rows)

    def draw(self, rng: np.random.Generator) -> dict:
        i = int(np.searchsorted(self.cum, rng.random() * self.cum[-1], side="right"))
        return self.rows[min(i, len(self.rows) - 1)]


def _pool(V: list[dict], splits: dict, split: str, alpha: float) -> Pool:
    vis = [r for r in V if splits[r["key"]] in ("all", split)]
    return Pool(vis, stratified_q(vis, alpha, bucket_masses(V, alpha)) if vis else None)


class NameSampler:
    def __init__(self, lex_dir: Path, split: str, sampling: dict, vocab: dict):
        self.s = sampling
        alpha, alpha_c = sampling["alpha"], sampling["alpha_cidade"]
        rows = load_rows(lex_dir)
        V = {k: [r for r in rows[k] if r["key"] in vocab[k]["splits"]] for k in rows}
        sp = {k: vocab[k]["splits"] for k in V}
        for r in V["prenome"] + V["sobrenome"]:
            dist = json.loads(r["formas"]) if r.get("formas") else {r["display"]: 1.0}
            r["_formas"] = (list(dist), np.cumsum(list(dist.values())))
        self.prenomes = {g: _pool([r for r in V["prenome"] if r["gender"] == g],
                                  sp["prenome"], split, alpha) for g in ("M", "F")}
        self.sobrenomes = _pool(V["sobrenome"], sp["sobrenome"], split, alpha)
        self.municipios = _pool(V["cidade"], sp["cidade"], split, alpha_c)

        # Inventados: partição pelo mesmo u (test < heldout_test <= val < ... <= train).
        vc = vocab["params"]
        def inv_split(u: float) -> str:
            if u < vc["heldout_test"]:
                return "test"
            return "val" if u < vc["heldout_test"] + vc["heldout_val"] else "train"
        inv = [r for r in read_csv(lex_dir / "inventados.csv") if inv_split(float(r["u"])) == split]
        self.inv_prenomes = {g: Pool([r for r in inv if r["kind"] == "prenome"
                                      and r["gender"] == g]) for g in ("M", "F")}
        self.inv_sobrenomes = Pool([r for r in inv if r["kind"] == "sobrenome"])

        self.particles = {r["key"]: json.loads(r["particulas"]) for r in V["sobrenome"]}
        self.estrutura = read_json(lex_dir / "estrutura.json")
        ns = self.estrutura["n_sobrenomes"]
        self.n_sob_values = np.array([int(k) for k in ns])
        self.n_sob_p = np.array(list(ns.values())) / sum(ns.values())

    # -- tokens ---------------------------------------------------------------
    @staticmethod
    def _spell(r: dict, rng) -> str:
        """Sorteia a grafia (com/sem acento) na proporção observada no TSE."""
        if "_formas" not in r:
            return r["display"]
        forms, cum = r["_formas"]
        return forms[min(int(np.searchsorted(cum, rng.random() * cum[-1], side="right")),
                         len(forms) - 1)]

    def prenome(self, rng, gender: str) -> Token:
        if rng.random() < self.s["p_invented"] and len(self.inv_prenomes[gender]):
            r = self.inv_prenomes[gender].draw(rng)
        else:
            r = self.prenomes[gender].draw(rng)
        return Token(self._spell(r, rng), "prenome", r["bucket"], r["key"])

    def sobrenome(self, rng) -> tuple[str | None, Token]:
        if rng.random() < self.s["p_invented"] and len(self.inv_sobrenomes):
            r = self.inv_sobrenomes.draw(rng)
            particle = None
        else:
            r = self.sobrenomes.draw(rng)
            dist = self.particles.get(r["key"]) or {"": 1.0}
            opts = list(dist)
            p = np.array(list(dist.values()))
            particle = opts[rng.choice(len(opts), p=p / p.sum())] or None
        return particle, Token(self._spell(r, rng), "sobrenome", r["bucket"], r["key"])

    def full_name(self, rng, gender: str | None = None) -> list[Token]:
        gender = gender or ("F" if rng.random() < 0.5 else "M")
        toks = [self.prenome(rng, gender)]
        if rng.random() < self.estrutura["p_prenome_composto"]:
            second = self.prenome(rng, gender)
            if second.key != toks[0].key:
                toks.append(second)
        n_sob = int(rng.choice(self.n_sob_values, p=self.n_sob_p))
        used = set()
        for _ in range(n_sob):
            particle, sob = self.sobrenome(rng)
            if sob.key in used:
                continue
            used.add(sob.key)
            if particle:
                toks.append(Token(particle.lower(), "particula", None, particle))
            toks.append(sob)
        p_ag = self.estrutura.get("p_agnome_por_genero", {}).get(gender, 0.0)
        if rng.random() < p_ag:
            dist = self.estrutura["agnomes"].get(gender) or {
                a: 1.0 for a in (AGNOMES_M if gender == "M" else AGNOMES_F)}
            opts = list(dist)
            p = np.array(list(dist.values()))
            toks.append(Token(opts[rng.choice(len(opts), p=p / p.sum())], "agnome", None, None))
        return toks

    def city(self, rng) -> tuple[Token, Token]:
        r = self.municipios.draw(rng)
        return Token(r["nome"], "cidade", r["bucket"], r["key"]), Token(r["uf"], "uf", None, r["uf"])

    # -- linhas ---------------------------------------------------------------
    def compose(self, rng, templates: list[dict]) -> dict:
        """Sorteia um template e preenche; devolve texto + spans de cada entidade."""
        w = np.array([t["weight"] for t in templates], dtype=float)
        tpl = templates[rng.choice(len(templates), p=w / w.sum())]
        city = None
        pieces: list[tuple[str, Token | None]] = []
        for part in re.split(r"(\{\w+\})", tpl["pattern"]):
            if not part:
                continue
            if part in ("{nome}", "{nome_m}", "{nome_f}"):
                gender = {"{nome_m}": "M", "{nome_f}": "F"}.get(part)
                for i, t in enumerate(self.full_name(rng, gender)):
                    if i:
                        pieces.append((" ", None))
                    pieces.append((t.text, t))
            elif part in ("{cidade}", "{uf}"):
                city = city or self.city(rng)
                t = city[0] if part == "{cidade}" else city[1]
                pieces.append((t.text, t))
            else:
                lead = part[: len(part) - len(part.lstrip())]
                trail = part[len(part.rstrip()):]
                core = part.strip()
                if lead:
                    pieces.append((lead, None))
                if core:
                    pieces.append((core, Token(core, "contexto", None, None)))
                if trail:
                    pieces.append((trail, None))

        upper = rng.random() < self.s["p_upper"]
        text, entities = "", []
        for s, tok in pieces:
            if upper:
                s = s.upper()
            if tok is not None:
                entities.append({"type": tok.type, "start": len(text), "end": len(text) + len(s),
                                 "bucket": tok.bucket, "key": tok.key})
            text += s
        return {"text": text, "template": tpl["id"], "upper": upper, "entities": entities}
