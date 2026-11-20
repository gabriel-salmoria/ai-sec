"""Registros (valores dos campos) para as páginas locais.

O ponto de partida são os próprios registros do OCRSD (os .json que acompanham cada PDF
baixado), que já são coerentes entre campos: datas por extenso e em dígitos, nome após o
casamento, filiação, município e UF. O OCRSD, porém, só usa 68 prenomes, 35 sobrenomes e
12 capitais. Aqui cada registro é "re-sorteado": todo prenome, sobrenome e capital é
trocado de forma consistente no documento inteiro por um sorteado do léxico do projeto,
respeitando a partição de nomes (o treino nunca recebe nomes reservados para o teste) e
uma lista de bloqueio (nomes inéditos do teste do BRESSAY). Identificadores numéricos
(CPF, matrícula, CNS...) recebem dígitos novos com a mesma máscara.

Regra de acentos: numa página escrita por um gerador neural (que não escreve acento, ç,
º, / nem Q/X/Z maiúsculos), os nomes e municípios sorteados são restritos a grafias que
ele escreve fielmente; os demais campos com esses caracteres são datilografados.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

import numpy as np

from ..common import load_config, read_csv, resolve
from ..sampler import NameSampler
from ..vocab import select_vocab

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_IDS = {"certidao_casamento", "certidao_casamento_cnj", "certidao_nascimento_cnj",
                "certidao_obito", "dnv"}
# Alfabeto do modelo de Graves (sjvasquez/handwriting-synthesis): sem acentos, ç, º, /,
# e sem Q, X, Z maiúsculos.
NEURAL_SAFE = set(" !\"#'(),-.0123456789:;?ABCDEFGHIJKLMNOPRSTUVWYabcdefghijklmnopqrstuvwxyz")
# Nomes inéditos do teste do BRESSAY (experiments/modelos/*/test_bressay.jsonl,
# visto_no_treino = False). Nunca entram nas páginas geradas.
BRESSAY_UNSEEN = {
    "prenome": {"ADELIAS", "ARISTOTE", "DIDEROT", "FLORESTAN", "FRANS", "GENE", "GREGOR", "IHOR",
                "JADAS", "JEROME", "JOHANNES", "LUTHER", "PANDORA", "RILLEY", "TAIWAN"},
    "sobrenome": {"ANGOLA", "BAILEY", "CORTICO", "FESTI", "GEORG", "JOANICO", "KANG", "LOVE",
                  "MAGNOLI", "MOSE", "NORA", "PERNAS", "REMOS", "SALAMANCA", "SEMENTE",
                  "SIMMEL", "SKINNER", "TUTU"},
}
ID_FIELDS = re.compile(r"cpf|matr[ií]cula|\bcns\b|cnes|cart[aã]o (nacional de )?sa[uú]de|cart[aã]o sus",
                       re.IGNORECASE)


def neural_safe(text: str) -> bool:
    return all(c in NEURAL_SAFE for c in text)


def key_of(s: str) -> str:
    """Chave do léxico: maiúsculas sem acento."""
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).upper()


def field_class(data_type: str | None, value: str) -> str:
    dt = data_type or ""
    if dt not in ("date", "time") and value and re.fullmatch(r"[\d\s.\-/:]+", value):
        return "number"
    if dt == "person_name":
        return "name"
    if dt == "municipality":
        return "place"
    if dt in ("uf", "enum", "checkbox"):
        return "closed"
    if dt in ("date", "time"):
        return "date"
    if dt in ("integer", "document", "digit_sequence", "dnv_number"):
        return "number"
    return "text"


# ----------------------------------------------------------------------------- vocabulário
@lru_cache(maxsize=1)
def vocab() -> dict:
    """Mesma seleção de vocabulário do treino de linhas (40 mil linhas, seed fixa)."""
    cfg = load_config(str(ROOT / "configs" / "default.yaml"))
    path = ROOT / "data" / "forms" / "vocab.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    v = select_vocab(cfg, resolve(cfg, "lexicon"), cfg["generate"]["n"]["train"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(v, ensure_ascii=False), encoding="utf-8")
    return v


@lru_cache(maxsize=4)
def sampler(split: str) -> NameSampler:
    cfg = load_config(str(ROOT / "configs" / "default.yaml"))
    smp = dict(cfg["sampling"])
    if split == "train" and os.environ.get("OCR06_ALPHA"):  # nomes raros mais frequentes no treino
        smp["alpha"] = float(os.environ["OCR06_ALPHA"])
    if split == "normal":  # lote de teste "normal": nomes de todo o vocabulário, na frequência real
        smp["alpha"] = 1.0
        return NameSampler(resolve(cfg, "lexicon"), "any", smp, vocab())
    return NameSampler(resolve(cfg, "lexicon"), split, smp, vocab())


# Grafias variantes (como as dos cartórios: Zimermann/Zimmermann, Souza/Sousa, Luiz/Luis).
# Ensinam o modelo a copiar a tinta letra a letra em vez de "corrigir" para o nome comum.
_VARIANTS = [(r"([bcdfglmnprst])\1", r"\1"), (r"(?<=[aeiou])([lmnrst])(?=[aeiou])", r"\1\1"),
             (r"y", "i"), (r"i(?=[aeiou]|$)", "y"), (r"(?<=[aeiou])s(?=[aeiou])", "z"),
             (r"(?<=[aeiou])z(?=[aeiou])", "s"), (r"z$", "s"), (r"s$", "z"), (r"ph", "f"),
             (r"th", "t"), (r"(?<!^)w", "v"), (r"k", "c"), (r"c(?=[aou])", "k"),
             (r"á", "a"), (r"é", "e"), (r"ê", "e"), (r"í", "i"), (r"ó", "o"), (r"ô", "o"), (r"ú", "u"),
             (r"(?<=[^aeiou])e$", "i"), (r"(?<=[^aeiou])o$", "u"), (r"u(?=[^aeiou]+[aeiou])", "o")]


def spelling_variant(tok: str, rng) -> str | None:
    """Uma variante ortográfica plausível de `tok` (uma regra), ou None."""
    low = tok.lower()
    rules = [(a, b) for a, b in _VARIANTS if re.search(a, low[1:] if a.startswith("(?<!^)") else low)]
    if not rules:
        return None
    a, b = rules[int(rng.integers(len(rules)))]
    ms = list(re.finditer(a, low))
    m = ms[int(rng.integers(len(ms)))] if ms else None
    if m is None:
        return None
    new = low[:m.start()] + m.expand(b) + low[m.end():]
    if new == low or len(new) < 3:
        return None
    if tok.isupper():
        return new.upper()
    return new[0].upper() + new[1:] if tok[0].isupper() else new


@lru_cache(maxsize=1)
def lexicon_tables():
    lex = ROOT / "data" / "lexicon"
    gender = {r["key"]: r["gender"] for r in read_csv(lex / "prenomes.csv")}
    cities = read_csv(lex / "municipios.csv")
    by_name_uf = {(r["nome"], r["uf"]): r for r in cities}
    by_uf: dict[str, list[dict]] = {}
    for r in cities:
        by_uf.setdefault(r["uf"], []).append(r)
    return gender, by_name_uf, by_uf


# ----------------------------------------------------------------------------- esqueletos
def ocrsd_skeletons(template: str) -> list[dict]:
    """Registros do OCRSD escritos com fonte (valores em português, já formatados)."""
    out = []
    for meta in sorted((ROOT / "data" / "ocrsd").glob("*/synthetic_*.json")):
        job = meta.parent / "job.json"
        mapping_id = json.loads(job.read_text())["options"].get("mapping_id") if job.exists() else None
        m = json.loads(meta.read_text(encoding="utf-8"))
        tid = m.get("source_template") or m["template_id"]
        if tid != template or (m.get("handwriting") or {}).get("model") not in (None, "font"):
            continue
        if template == "dnv" and mapping_id != "mapeamento_seguindo_norma":
            continue
        m["_id"] = f"{meta.parent.name}/{meta.stem}"
        out.append(m)
    return out


@lru_cache(maxsize=8)
def mapping_fields(template: str) -> dict[str, dict]:
    m = json.loads((ROOT / "data" / "forms" / template / "mapping.json").read_text(encoding="utf-8"))
    return {f["field_id"]: f for f in m["fields"]}


def data_types(template: str) -> dict[str, str]:
    return {k: f.get("data_type") for k, f in mapping_fields(template).items()}


@lru_cache(maxsize=1)
def ocrsd_name_pools() -> tuple[set[str], set[str], dict[str, str]]:
    """Prenomes, sobrenomes e municípios (-> UF) usados pelo OCRSD nos cinco modelos."""
    from collections import Counter
    first_c, sur_c, places = Counter(), Counter(), set()
    for meta in (ROOT / "data" / "ocrsd").glob("*/synthetic_*.json"):
        m = json.loads(meta.read_text(encoding="utf-8"))
        tid = m.get("source_template") or m["template_id"]
        if tid not in TEMPLATE_IDS:
            continue
        dts = data_types(tid)
        for f in m["fields"]:
            v = f.get("requested_value") or f.get("value") or ""
            dt = dts.get(f["field_id"])
            if dt == "person_name":
                for part in re.split(r"[;,]| e ", v):
                    toks = [t for t in part.split() if t[:1].isupper()]
                    if toks:
                        first_c[toks[0]] += 1
                        sur_c.update(toks[1:])
            elif dt == "municipality" and v:
                places.add(v)
    gender, by_name_uf, _ = lexicon_tables()
    first = {t for t, n in first_c.items() if n >= 10 and key_of(t) in gender}
    sur = {t for t, n in sur_c.items() if n >= 10} - first
    cities = {}
    for name in places:  # a capital é o município mais populoso com esse nome
        cands = [r for (n, _), r in by_name_uf.items() if n == name]
        if cands:
            cities[name] = max(cands, key=lambda r: float(r["pop"]))["uf"]
    return first, sur, cities


# ----------------------------------------------------------------------------- re-sorteio
def _draw(fn, rng, ok, tries=60):
    for _ in range(tries):
        v = fn()
        if ok(v):
            return v
    return None


def remap_record(skel: dict, split: str, neural: bool, rng: np.random.Generator) -> dict:
    """Troca nomes, capitais e identificadores de um registro do OCRSD, de forma consistente."""
    if split == "test" and os.environ.get("OCR06_NAMES") == "normal":
        split = "normal"  # mãos, fontes e esqueletos continuam os de teste; só os nomes mudam
    s = sampler(split)
    gender, by_name_uf, by_uf = lexicon_tables()
    first_pool, sur_pool, city_pool = ocrsd_name_pools()
    vc = vocab()
    allowed = {k: {key for key, sp in vc[k]["splits"].items() if split == "normal" or sp in ("all", split)}
               for k in ("prenome", "sobrenome", "cidade")}

    def ok_name(tok, kind) -> bool:
        k = key_of(tok)
        return (k not in BRESSAY_UNSEEN.get(kind, set()) and k in allowed[kind]
                and (not neural or neural_safe(tok)) and tok not in first_pool | sur_pool)

    p_var = float(os.environ.get("OCR06_P_VARIANT", "0")) if split == "train" else 0.0
    held = {k: {key for key, sp in vc[k]["splits"].items() if sp not in ("all", "train")}
            for k in ("prenome", "sobrenome")}

    def vary(tok, kind):
        """Com prob. p_var, troca por uma grafia variante que não seja nome de teste/BRESSAY."""
        if not tok or rng.random() >= p_var:
            return tok
        v = spelling_variant(tok, rng)
        if not v:
            return tok
        k = key_of(v)
        if k in held[kind] or k in BRESSAY_UNSEEN.get(kind, set()) or (neural and not neural_safe(v)):
            return tok
        return v

    texts = [f.get("value") or "" for f in skel["fields"]]
    joined = "\n".join(texts)
    mapping: dict[str, str] = {}
    for tok in sorted(first_pool):
        if re.search(rf"\b{re.escape(tok)}\b", joined, re.IGNORECASE):
            g = gender.get(key_of(tok), "F")
            new = _draw(lambda: s.prenome(rng, g).text, rng, lambda t: ok_name(t, "prenome"))
            if new:
                mapping[tok] = vary(new, "prenome")
    for tok in sorted(sur_pool):
        if re.search(rf"\b{re.escape(tok)}\b", joined, re.IGNORECASE):
            new = _draw(lambda: s.sobrenome(rng)[1].text, rng, lambda t: ok_name(t, "sobrenome"))
            if new:
                mapping[tok] = vary(new, "sobrenome")
    # Capitais: cada UF antiga vai para uma UF nova; cada capital, para um município dessa UF.
    uf_map, city_map, code_map = {}, {}, {}
    for city, uf in sorted(city_pool.items()):
        if city not in joined and city.upper() not in joined:
            continue
        old = by_name_uf.get((city, uf))
        if uf not in uf_map:
            r = s.municipios.draw(rng)
            uf_map[uf] = r["uf"]
        cands = [r for r in by_uf[uf_map[uf]] if r["id"] in allowed["cidade"]
                 and (not neural or neural_safe(r["nome"]))]
        if not cands:
            continue
        w = np.array([float(r["pop"]) for r in cands]) ** 0.5
        new = cands[int(rng.choice(len(cands), p=w / w.sum()))]
        city_map[city] = new["nome"]
        if old:
            code_map[old["id"]] = new["id"]

    def sub(text: str) -> str:
        if not text:
            return text
        # Municípios viram marcadores antes dos nomes ("Paulo" em "São Paulo" não é nome).
        held = {}
        for i, (old, new) in enumerate(sorted(city_map.items(), key=lambda kv: -len(kv[0]))):
            for o, n in ((old, new), (old.upper(), new.upper())):
                tag = f"\x00{len(held)}\x00"
                if o in text:
                    text = text.replace(o, tag)
                    held[tag] = n
        for old, new in sorted(mapping.items(), key=lambda kv: -len(kv[0])):
            text = re.sub(rf"\b{re.escape(old)}\b", new, text)
            text = re.sub(rf"\b{re.escape(old.upper())}\b", new.upper(), text)
        for old, new in uf_map.items():
            text = re.sub(rf"(?<![A-Za-z]){old}(?![A-Za-z])", new, text)
        for old, new in code_map.items():
            text = text.replace(old, new)
        for tag, n in held.items():
            text = text.replace(tag, n)
        return text

    tid = skel.get("source_template") or skel["template_id"]
    fields = []
    for f in skel["fields"]:
        g = {k: f[k] for k in ("field_id", "label", "bbox") if k in f}
        g["value"] = sub(f.get("value") or "")
        g["blank"] = bool(f.get("blank")) or not g["value"]
        mf = mapping_fields(tid).get(f["field_id"], {})
        is_id = ID_FIELDS.search(f["field_id"]) or ID_FIELDS.search(mf.get("label") or "")
        if is_id and mf.get("data_type") not in ("date", "time") and re.fullmatch(r"[\d.\-/ ]+", g["value"] or "x"):
            g["value"] = re.sub(r"\d", lambda _: str(int(rng.integers(10))), g["value"])
        if f.get("elements"):
            els = []
            digits = [c for c in g["value"] if c.isdigit()] if any("index" in e for e in f["elements"]) else []
            for e in f["elements"]:
                e2 = {k: e[k] for k in ("element_id", "label", "bbox", "checked", "index") if k in e}
                if "index" in e and digits:
                    e2["value"] = digits[e["index"]] if e["index"] < len(digits) else ""
                elif "value" in e:
                    e2["value"] = e["value"]
                els.append(e2)
            g["elements"] = els
        fields.append(g)
    return {"skeleton": skel["_id"], "template": skel.get("source_template") or skel["template_id"],
            "split": split, "neural": neural, "fields": fields,
            "remap": {"names": mapping, "cities": city_map, "uf": uf_map}}
