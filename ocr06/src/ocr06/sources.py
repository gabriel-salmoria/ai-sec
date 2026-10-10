"""Coleta das fontes públicas: IBGE (prenomes, municípios, população), TSE e RFB.

TSE e RFB publicam nomes completos de pessoas reais (candidatos e sócios de empresas).
Esses arquivos são lidos em streaming e só estatísticas agregadas por token são
mantidas (contagem de sobrenomes, partículas, formas acentuadas, estrutura do nome).
Nenhum nome completo é gravado em disco; os .zip são apagados ao fim (keep_raw=false).
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import requests
from tqdm import tqdm

from .common import download, get_json, read_json, resolve, write_json
from .text import key, parse_full_name


# --------------------------------------------------------------------------- IBGE

def fetch_prenomes(cfg: dict) -> list[dict]:
    """Lista completa de prenomes do Censo 2010 (espelho Brasil.IO dos dados do IBGE)."""
    raw = resolve(cfg, "raw")
    path = download(cfg["sources"]["prenomes_url"], raw / "prenomes_ibge2010.csv.gz")
    with gzip.open(path, "rt", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        out.append({
            "key": r["first_name"],
            "freq": int(r["frequency_total"] or 0),
            "freq_f": int(r["frequency_female"] or 0),
            "freq_m": int(r["frequency_male"] or 0),
            "gender": r["classification"],
            "group": r["group_name"],
            "group_freq": int(r["frequency_group"] or 0),
        })
    return out


def validate_prenomes(cfg: dict, prenomes: list[dict]) -> dict:
    """Compara o top-20 da API oficial do IBGE com o espelho usado."""
    api = get_json(cfg["sources"]["ibge_ranking_url"])[0]["res"]
    local = {p["key"]: p["freq"] for p in prenomes}
    mismatches = [
        {"nome": r["nome"], "api": r["frequencia"], "espelho": local.get(r["nome"])}
        for r in api if local.get(r["nome"]) != r["frequencia"]
    ]
    return {"checked": len(api), "mismatches": mismatches}


def fetch_municipios(cfg: dict) -> list[dict]:
    raw = resolve(cfg, "raw")
    mun_path = raw / "municipios.json"
    pop_path = raw / "populacao_censo2022.json"
    if not mun_path.exists():
        write_json(mun_path, get_json(cfg["sources"]["municipios_url"]))
    if not pop_path.exists():
        write_json(pop_path, get_json(cfg["sources"]["populacao_url"]))
    muns = read_json(mun_path)
    pop = {}
    for s in read_json(pop_path)[0]["resultados"][0]["series"]:
        v = next(iter(s["serie"].values()))
        if v and v.isdigit():
            pop[int(s["localidade"]["id"])] = int(v)

    out = []
    for m in muns:
        uf = None
        if m.get("microrregiao"):
            uf = m["microrregiao"]["mesorregiao"]["UF"]["sigla"]
        elif m.get("regiao-imediata"):
            uf = m["regiao-imediata"]["regiao-intermediaria"]["UF"]["sigla"]
        out.append({"id": m["id"], "nome": m["nome"], "uf": uf, "pop": pop.get(m["id"], 0)})
    return out


# --------------------------------------------------------------- Agregação de nomes

class NameAggregator:
    """Acumula estatísticas por token a partir de nomes completos, sem guardá-los.

    O 2º token ambíguo (prenome composto ou sobrenome) é guardado à parte, junto com
    o nº de sobrenomes restantes, e resolvido depois em `lexicon.resolve_candidates`.
    """

    def __init__(self):
        self.seen: set[int] = set()
        self.surname = defaultdict(Counter)       # fonte -> Counter(sobrenome)
        self.last = Counter()                     # último sobrenome (evidência de sobrenome)
        self.candidate = defaultdict(Counter)     # fonte -> Counter("CHAVE|n_restantes")
        self.particles = defaultdict(Counter)     # sobrenome -> Counter(partícula ou "")
        self.forms = defaultdict(Counter)         # chave -> Counter(grafia com acento), só TSE
        self.agnome = Counter()
        self.n_people = Counter()
        self.n_rejected = Counter()

    def add(self, full_name: str, source: str, collect_forms: bool) -> None:
        full_name = " ".join(full_name.upper().split())
        h = int.from_bytes(hashlib.blake2b(full_name.encode(), digest_size=8).digest(), "big")
        if h in self.seen:
            return
        self.seen.add(h)
        parsed = parse_full_name(full_name)
        if parsed is None:
            self.n_rejected[source] += 1
            return
        first, candidate, surnames, agnome = parsed
        self.n_people[source] += 1
        self.candidate[source][f"{key(candidate) if candidate else ''}|{len(surnames)}"] += 1
        if agnome:
            self.agnome[key(agnome)] += 1
        for particle, s in surnames:
            k = key(s)
            self.surname[source][k] += 1
            self.particles[k][key(particle) if particle else ""] += 1
        self.last[key(surnames[-1][1])] += 1
        if collect_forms:
            for t in [first, candidate] + [s for _, s in surnames]:
                if t:
                    self.forms[key(t)][t] += 1

    def to_json(self) -> dict:
        # Grafias: só as que somam >= 5% das ocorrências da chave (ex.: JOSÉ e JOSE).
        forms = {}
        for k, c in self.forms.items():
            tot = sum(c.values())
            kept = {f: v for f, v in c.items() if v / tot >= 0.05}
            if set(kept) != {k}:
                forms[k] = kept
        return {
            "surname": {src: dict(c) for src, c in self.surname.items()},
            "last": dict(self.last),
            "candidate": {src: dict(c) for src, c in self.candidate.items()},
            "particles": {k: dict(c) for k, c in self.particles.items()},
            "forms": forms,
            "agnome": dict(self.agnome),
            "n_people": dict(self.n_people),
            "n_rejected": dict(self.n_rejected),
        }


# ---------------------------------------------------------------------------- TSE

def ingest_tse(cfg: dict, agg: NameAggregator) -> list[str]:
    raw = resolve(cfg, "raw")
    used = []
    for year in cfg["sources"]["tse"]["years"]:
        url = cfg["sources"]["tse"]["url"].format(year=year)
        path = download(url, raw / f"tse_consulta_cand_{year}.zip")
        with zipfile.ZipFile(path) as zf:
            members = [m for m in zf.namelist() if m.lower().endswith(".csv")]
            for m in tqdm(members, desc=f"TSE {year}", leave=False):
                with zf.open(m) as fb:
                    reader = csv.reader(io.TextIOWrapper(fb, encoding="latin-1"), delimiter=";")
                    header = next(reader)
                    col = header.index("NM_CANDIDATO")
                    for row in reader:
                        if len(row) > col:
                            agg.add(row[col], "tse", collect_forms=True)
        used.append(url)
        if not cfg["sources"]["keep_raw"]:
            path.unlink()
    return used


# ---------------------------------------------------------------------------- RFB

def _rfb_latest_month(webdav: str, token: str) -> str:
    r = requests.request("PROPFIND", webdav, auth=(token, ""), headers={"Depth": "1"}, timeout=60)
    r.raise_for_status()
    months = sorted(set(re.findall(r"/(\d{4}-\d{2})/", r.text)))
    if not months:
        raise RuntimeError("Nenhum mês encontrado no WebDAV da RFB (share_token mudou?)")
    return months[-1]


def ingest_rfb(cfg: dict, agg: NameAggregator) -> list[str]:
    rc = cfg["sources"]["rfb"]
    raw = resolve(cfg, "raw")
    webdav, token = rc["webdav_url"], rc["share_token"]
    month = _rfb_latest_month(webdav, token) if rc["month"] == "latest" else rc["month"]
    used = []
    for n in rc["shards"]:
        url = f"{webdav}{month}/Socios{n}.zip"
        path = download(url, raw / f"rfb_{month}_Socios{n}.zip", auth=(token, ""))
        with zipfile.ZipFile(path) as zf:
            for m in zf.namelist():
                with zf.open(m) as fb:
                    reader = csv.reader(io.TextIOWrapper(fb, encoding="latin-1"), delimiter=";")
                    for row in tqdm(reader, desc=f"RFB Socios{n}", unit=" linhas", leave=False):
                        # identificador_socio: 1 = PJ, 2 = pessoa física, 3 = estrangeiro
                        if len(row) > 2 and row[1] == "2":
                            agg.add(row[2], "rfb", collect_forms=False)
        used.append(url)
        if not cfg["sources"]["keep_raw"]:
            path.unlink()
    return used
