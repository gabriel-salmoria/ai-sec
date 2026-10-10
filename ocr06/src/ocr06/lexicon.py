"""Constrói o léxico agregado: prenomes, sobrenomes, municípios e nomes inventados.

Saídas em data/lexicon/:
  prenomes.csv, sobrenomes.csv, municipios.csv, inventados.csv  (um token por linha)
  estrutura.json  (distribuição de nº de sobrenomes, prenome composto, agnomes)
  meta.json       (fontes, datas, contagens e itens descartados)
Cada token recebe um `bucket` (comum/raro/inventado, relativo à população inteira) e
um número `u` em [0, 1) estável por token. A seleção do vocabulário por frequência e a
reserva de nomes para validação/teste são feitas em `vocab.py`, a partir dessas colunas.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone

import numpy as np

from .common import read_json, resolve, stable_unit, write_csv, write_json
from .sources import (NameAggregator, fetch_municipios, fetch_prenomes, ingest_rfb, ingest_tse,
                      validate_prenomes)
from .text import PARTICLES, display, levenshtein, valid_token

AGNOME_DISPLAY = {"JUNIOR": "Júnior", "JR": "Júnior", "FILHO": "Filho", "NETO": "Neto",
                  "SOBRINHO": "Sobrinho", "FILHA": "Filha", "NETA": "Neta", "SOBRINHA": "Sobrinha"}
AGNOME_GENDER = {"Júnior": "M", "Filho": "M", "Neto": "M", "Sobrinho": "M",
                 "Filha": "F", "Neta": "F", "Sobrinha": "F"}


def filter_prenomes(prenomes: list[dict], lc: dict) -> tuple[list[dict], Counter]:
    """Remove grafias que parecem erro de digitação do censo (MMARIA, MAARIA...)."""
    head_freq = {p["key"]: p["freq"] for p in prenomes}
    kept, dropped = [], Counter()
    for p in prenomes:
        k = p["key"]
        if p["freq"] < lc["prenome_min_freq"] or not re.fullmatch(r"[A-Z]{2,}", k):
            dropped["formato_ou_freq"] += 1
            continue
        if re.search(r"(.)\1\1", k) or re.match(r"(.)\1", k):
            dropped["letra_repetida"] += 1
            continue
        g = p["group"]
        gfreq = head_freq.get(g, p["group_freq"])
        if (g and k != g and gfreq and p["freq"] / gfreq < lc["prenome_typo_ratio"]
                and levenshtein(k, g) == 1):
            dropped["variante_rara_de_grupo"] += 1
            continue
        kept.append(p)
    return kept, dropped


def spellings(forms: dict, k: str) -> tuple[str, str]:
    """Grafias observadas no TSE (ex.: José 60%, Jose 40%) -> (mais comum, JSON da distribuição)."""
    c = forms.get(k) or {k: 1}
    tot = sum(c.values())
    dist = {display(f): round(v / tot, 4) for f, v in sorted(c.items(), key=lambda x: -x[1])}
    return next(iter(dist)), json.dumps(dist, ensure_ascii=False)


def resolve_candidates(agg: dict, prenome_freq: dict[str, int]):
    """Decide se o 2º token ambíguo é prenome composto ou sobrenome.

    Compara a taxa do token como prenome no Censo (freq / total de pessoas) com a taxa
    dele como último sobrenome nas fontes. Ex.: PEDRO é muito mais comum como prenome
    (JOÃO PEDRO), SANTOS como sobrenome (MARIA SANTOS SILVA).
    """
    n_people = sum(agg["n_people"].values())
    total_prenomes = sum(prenome_freq.values())
    last = agg["last"]
    per_source = {src: Counter(c) for src, c in agg["surname"].items()}
    n_sur, decisions = Counter(), Counter()
    composto = 0
    for src, cands in agg["candidate"].items():
        for kc, c in cands.items():
            k, n = kc.rsplit("|", 1)
            n = int(n)
            if not k:
                n_sur[n] += c
            elif prenome_freq.get(k, 0) / total_prenomes > last.get(k, 0) / n_people:
                n_sur[n] += c
                composto += c
                decisions["prenome_composto"] += c
            else:
                n_sur[n + 1] += c
                per_source[src][k] += c
                agg["particles"].setdefault(k, {})
                agg["particles"][k][""] = agg["particles"][k].get("", 0) + c
                decisions["sobrenome"] += c
    return per_source, n_sur, composto / max(n_people, 1), decisions


def assign_buckets(rows: list[dict], weight: str, common_mass: float) -> None:
    order = sorted(rows, key=lambda r: -r[weight])
    total = sum(r[weight] for r in rows) or 1
    acc = 0.0
    for r in order:
        r["bucket"] = "comum" if acc < common_mass else "raro"
        acc += r[weight] / total


class CharNgram:
    """Modelo de n-gramas de caracteres para inventar nomes plausíveis."""

    def __init__(self, words: list[str], n: int):
        self.n = n
        counts = defaultdict(Counter)
        for w in words:
            s = "^" * (n - 1) + w + "$"
            for i in range(n - 1, len(s)):
                counts[s[i - n + 1:i]][s[i]] += 1
        self.alphabet = sorted({c for c_ in counts.values() for c in c_})
        self.table = {}
        for ctx, c in counts.items():
            chars = list(c)
            p = np.array([c[ch] for ch in chars], dtype=float)
            self.table[ctx] = (chars, p / p.sum(), c, sum(c.values()))

    def sample(self, rng: np.random.Generator, max_len: int) -> str:
        ctx, out = "^" * (self.n - 1), ""
        while len(out) <= max_len:
            chars, p, _, _ = self.table[ctx]
            ch = chars[rng.choice(len(chars), p=p)]
            if ch == "$":
                break
            out += ch
            ctx = (ctx + ch)[-(self.n - 1):]
        return out

    def avg_logprob(self, w: str, k: float = 0.01) -> float:
        s = "^" * (self.n - 1) + w + "$"
        V = len(self.alphabet)
        lp = 0.0
        for i in range(self.n - 1, len(s)):
            ctx, ch = s[i - self.n + 1:i], s[i]
            _, _, c, tot = self.table.get(ctx, (None, None, Counter(), 0))
            lp += np.log((c[ch] + k) / (tot + k * V))
        return lp / (len(s) - self.n + 1)


def invent(words: list[str], forbidden: set[str], n_out: int, ic: dict,
           rng: np.random.Generator) -> list[str]:
    model = CharNgram(words, ic["ngram_order"])
    threshold = float(np.quantile([model.avg_logprob(w) for w in words],
                                  ic["plausibility_quantile"]))
    out: set[str] = set()
    attempts = 0
    while len(out) < n_out and attempts < n_out * 200:
        attempts += 1
        w = model.sample(rng, ic["max_len"])
        if (ic["min_len"] <= len(w) <= ic["max_len"] and w not in forbidden and w not in out
                and not re.search(r"(.)\1\1", w) and model.avg_logprob(w) >= threshold):
            out.add(w)
    return sorted(out)


def build(cfg: dict) -> None:
    lex_dir = resolve(cfg, "lexicon")
    lc, seed = cfg["lexicon"], cfg["seed"]
    rng = np.random.default_rng(seed)

    print("[1/5] Prenomes (IBGE, Censo 2010)")
    prenomes = fetch_prenomes(cfg)
    validation = validate_prenomes(cfg, prenomes)
    n_raw = len(prenomes)
    raw_freq = {p["key"]: p["freq"] for p in prenomes}
    prenomes, dropped_prenomes = filter_prenomes(prenomes, lc)

    print("[2/5] Sobrenomes e acentos (TSE + RFB)")
    agg_path = lex_dir / "_agregado_nomes.json"
    if not agg_path.exists():
        aggregator = NameAggregator()
        urls = ingest_tse(cfg, aggregator) + ingest_rfb(cfg, aggregator)
        write_json(agg_path, {**aggregator.to_json(), "urls": urls})
    agg = read_json(agg_path)
    forms = agg["forms"]
    per_source, n_sur, p_composto, decisions = resolve_candidates(agg, raw_freq)

    for p in prenomes:
        p["display"], p["formas"] = spellings(forms, p["key"])
        p["u"] = round(stable_unit(seed, "token", p["key"]), 6)
    assign_buckets(prenomes, "freq", lc["common_mass"])

    total = Counter()
    for c in per_source.values():
        total.update(c)
    sobrenomes, dropped_sob = [], Counter()
    for k, c in total.items():
        if k in PARTICLES or not valid_token(k):
            dropped_sob["invalido"] += 1
        elif c < lc["sobrenome_min_count"]:
            dropped_sob["abaixo_min_count"] += 1
        else:
            pc = agg["particles"].get(k, {})
            tot = sum(pc.values()) or 1
            sobrenomes.append({
                "key": k, **dict(zip(("display", "formas"), spellings(forms, k))), "freq": c,
                "freq_tse": per_source.get("tse", {}).get(k, 0),
                "freq_rfb": per_source.get("rfb", {}).get(k, 0),
                "particulas": json.dumps({p: round(v / tot, 4) for p, v in pc.items()
                                          if v / tot >= 0.01}),
                "u": round(stable_unit(seed, "token", k), 6),
            })
    assign_buckets(sobrenomes, "freq", lc["common_mass"])

    print("[3/5] Municípios (IBGE) e população (Censo 2022)")
    municipios = [m for m in fetch_municipios(cfg) if m["pop"] > 0 and m["uf"]]
    for m in municipios:
        m["u"] = round(stable_unit(seed, "municipio", m["id"]), 6)
    assign_buckets(municipios, "pop", lc["common_mass"])

    print("[4/5] Nomes inventados (n-gramas de caracteres)")
    ic = lc["invented"]
    forbidden = {p["key"] for p in prenomes} | {s["key"] for s in sobrenomes}
    inventados = []
    for gender in ("F", "M"):
        words = [p["key"] for p in prenomes if p["gender"] == gender and p["freq"] >= 100]
        for w in invent(words, forbidden, ic["n_prenomes"] // 2, ic, rng):
            inventados.append({"key": w, "display": display(w), "kind": "prenome",
                               "gender": gender})
            forbidden.add(w)
    words = [s["key"] for s in sobrenomes if s["freq"] >= 20]
    for w in invent(words, forbidden, ic["n_sobrenomes"], ic, rng):
        inventados.append({"key": w, "display": display(w), "kind": "sobrenome", "gender": ""})
    for r in inventados:
        r["bucket"] = "inventado"
        r["u"] = round(stable_unit(seed, "token", r["key"]), 6)

    print("[5/5] Estrutura dos nomes e gravação")
    n_people = sum(agg["n_people"].values())
    capped = Counter()
    for k, v in n_sur.items():
        capped[min(k, 4)] += v
    agnomes = {"M": Counter(), "F": Counter()}
    for k, v in agg["agnome"].items():
        a = AGNOME_DISPLAY[k]
        agnomes[AGNOME_GENDER[a]][a] += v
    estrutura = {
        "n_sobrenomes": {str(k): v / sum(capped.values()) for k, v in sorted(capped.items())},
        "p_prenome_composto": p_composto,
        "p_agnome": sum(sum(c.values()) for c in agnomes.values()) / max(n_people, 1),
        # P(agnome | gênero), supondo metade das pessoas de cada gênero.
        "p_agnome_por_genero": {g: 2 * sum(c.values()) / max(n_people, 1)
                                for g, c in agnomes.items()},
        "agnomes": {g: {a: v / sum(c.values()) for a, v in c.items()}
                    for g, c in agnomes.items() if c},
    }

    prenomes.sort(key=lambda r: -r["freq"])
    sobrenomes.sort(key=lambda r: -r["freq"])
    municipios.sort(key=lambda r: -r["pop"])
    write_csv(lex_dir / "prenomes.csv", prenomes,
              ["key", "display", "formas", "freq", "gender", "bucket", "u"])
    write_csv(lex_dir / "sobrenomes.csv", sobrenomes,
              ["key", "display", "formas", "freq", "freq_tse", "freq_rfb", "particulas",
               "bucket", "u"])
    write_csv(lex_dir / "municipios.csv", municipios,
              ["id", "nome", "uf", "pop", "bucket", "u"])
    write_csv(lex_dir / "inventados.csv", inventados,
              ["key", "display", "kind", "gender", "bucket", "u"])
    write_json(lex_dir / "estrutura.json", estrutura)

    def summary(rows):
        return {"total": len(rows),
                "por_bucket": dict(Counter(r["bucket"] for r in rows))}

    write_json(lex_dir / "meta.json", {
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seed": seed,
        "fontes": {
            "prenomes": cfg["sources"]["prenomes_url"],
            "municipios": cfg["sources"]["municipios_url"],
            "populacao": cfg["sources"]["populacao_url"],
            "nomes_completos": agg.get("urls", []),
        },
        "validacao_ibge_top20": validation,
        "prenomes": {"brutos": n_raw, "descartados": dict(dropped_prenomes), **summary(prenomes)},
        "sobrenomes": {"descartados": dict(dropped_sob), **summary(sobrenomes)},
        "municipios": summary(municipios),
        "inventados": summary(inventados),
        "pessoas_agregadas": agg["n_people"],
        "segundo_token_resolvido_como": dict(decisions),
        "nomes_rejeitados_no_parsing": agg["n_rejected"],
    })
    print(f"  prenomes={len(prenomes)} sobrenomes={len(sobrenomes)} "
          f"municipios={len(municipios)} inventados={len(inventados)}")
