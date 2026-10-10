"""BRESSAY: download, extração das linhas, limpeza das marcações e marcação de nomes.

O BRESSAY (Zenodo, CC-BY 4.0) tem 1.000 redações manuscritas, uma por autor, com
transcrição por linha. Usamos a partição oficial por página (= por autor), então
nenhuma caligrafia do teste aparece no treino.

Saída em data/bressay/<split>/labels.jsonl, no mesmo formato do dataset sintético:
  id, image (relativo a data/), text, entities [{type, start, end, bucket, key}], page
`entities` marca nomes do léxico (prenome/sobrenome/cidade) achados por heurística;
data/bressay/nomes_para_revisao.csv lista todos para conferência manual.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image
from tqdm import tqdm

from .common import download, get_json, read_csv, resolve, write_json
from .text import key

SPLIT_FILES = {"train": "training.txt", "val": "validation.txt", "test": "test.txt"}
ILLEGIBLE = ("@@???@@", "--xxx--")
CROSSED = re.compile(r"--(?!xxx--)(.+?)--")
SUPSUB = re.compile(r"(##|\$\$)(.*?)\1")
WORD = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ']+")


# ----------------------------------------------------------------- download

def fetch(cfg: dict) -> Path:
    """Baixa o zip do Zenodo, confere o MD5 e extrai só as linhas e a partição."""
    raw = resolve(cfg, "raw") / "bressay"
    root = raw / "bressay"
    if (raw / ".extraido").exists():
        return root
    rec = get_json(f"https://zenodo.org/api/records/{cfg['bressay']['record']}")
    f = rec["files"][0]
    zpath = download(f["links"]["self"], raw / f["key"])
    algo, expected = f["checksum"].split(":")
    h = hashlib.new(algo)
    with open(zpath, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    if h.hexdigest() != expected:
        zpath.unlink()
        raise RuntimeError(f"checksum do BRESSAY não confere ({h.hexdigest()} != {expected}); "
                           "arquivo apagado, rode de novo")
    with zipfile.ZipFile(zpath) as zf:
        members = [m for m in zf.namelist()
                   if m.startswith(("bressay/data/lines/", "bressay/sets/"))
                   or m == "bressay/README.md"]
        for m in tqdm(members, desc="extraindo BRESSAY (linhas)", leave=False):
            zf.extract(m, raw)
    (raw / ".extraido").write_text(expected)
    return root


# ----------------------------------------------------------------- limpeza

def clean(text: str, bc: dict) -> tuple[str | None, str]:
    """Aplica a política de marcações. Retorna (texto ou None se descartada, motivo)."""
    if bc["drop_illegible"] and any(m in text for m in ILLEGIBLE):
        return None, "ilegivel"
    if CROSSED.search(text):
        mode = bc["crossed_out"]
        if mode == "drop_line":
            return None, "riscado"
        text = CROSSED.sub(r"\1" if mode == "keep_text" else "", text)
    text = SUPSUB.sub(r"\2", text)
    text = " ".join(text.split())
    if not text:
        return None, "vazia"
    return text, "ok"


# ----------------------------------------------------------- marcação de nomes

CITY_PREPS = {"em", "para", "no", "na", "até"}


def _lexicon_index(lex_dir: Path):
    """Por tipo: chave -> (bucket, taxa relativa); municípios (inclusive compostos)."""
    idx = {}
    for kind, fname in (("prenome", "prenomes.csv"), ("sobrenome", "sobrenomes.csv")):
        rows = read_csv(lex_dir / fname)
        tot = sum(float(r["freq"]) for r in rows)
        idx[kind] = {r["key"]: (r["bucket"], float(r["freq"]) / tot) for r in rows}
    cities = {}
    for r in read_csv(lex_dir / "municipios.csv"):
        cities[key(r["nome"])] = (r["id"], r["bucket"])
    max_words = max(len(c.split()) for c in cities)
    return idx, cities, max_words


def find_names(lines: list[dict], lex_dir: Path, stopwords: set[str]) -> None:
    """Marca prenomes, sobrenomes e municípios nas linhas (in-place, em `entities`).

    Heurística: palavra com inicial maiúscula fora de início de frase, presente no
    léxico e que no próprio BRESSAY aparece mais vezes capitalizada do que em
    minúscula (isso separa "Rosa" nome de "rosa" flor, "Estado" de "estado").
    Municípios compostos ("São José dos Campos") são casados pela maior sequência.
    """
    idx, cities, max_words = _lexicon_index(lex_dir)
    lower, upper = Counter(), Counter()
    by_page = defaultdict(list)
    for ln in lines:
        by_page[ln["page"]].append(ln)
        for m in WORD.finditer(ln["text"]):
            w = m.group()
            (upper if w[0].isupper() else lower)[key(w)] += 1

    stop = {key(s) for s in stopwords}
    for page_lines in by_page.values():
        page_lines.sort(key=lambda x: (x["paragraph"], x["line"]))
        prev_text, prev_par = "", None
        for ln in page_lines:
            words = list(WORD.finditer(ln["text"]))
            ents = []
            i = 0
            while i < len(words):
                m = words[i]
                w = m.group()
                before = ln["text"][:m.start()].rstrip()
                if not before:  # 1ª palavra da linha: olha o fim da linha anterior
                    before = prev_text.rstrip() if prev_par == ln["paragraph"] else ""
                sentence_start = not before or before[-1] in ".!?:;\"“"
                if (not w[0].isupper() or sentence_start or (w.isupper() and len(w) > 1)
                        or key(w) in stop):
                    i += 1
                    continue
                # Município: maior sequência de palavras que forma um nome do IBGE.
                # Palavra única que também é nome (Assis, Santos) só vira cidade
                # depois de "em/para/no/na/até".
                prev_word = words[i - 1].group().lower() if i else ""
                is_name = any(key(w) in idx[t] for t in ("prenome", "sobrenome"))
                matched = False
                for n in range(min(max_words, len(words) - i), 0, -1):
                    span = ln["text"][m.start():words[i + n - 1].end()]
                    k = key(span)
                    if k in cities and (n > 1 or (upper[k] > lower[k] and
                                                  (prev_word in CITY_PREPS or not is_name))):
                        cid, bucket = cities[k]
                        ents.append({"type": "cidade", "start": m.start(),
                                     "end": words[i + n - 1].end(), "bucket": bucket,
                                     "key": cid, "texto": span})
                        i += n
                        matched = True
                        break
                if matched:
                    continue
                k = key(w)
                kinds = [t for t in ("prenome", "sobrenome") if k in idx[t]]
                if upper[k] > lower[k] and kinds:
                    # Nos dois léxicos (ANDRADE, MARIA): fica o tipo de maior taxa relativa.
                    t = max(kinds, key=lambda t: idx[t][k][1])
                    ents.append({"type": t, "start": m.start(), "end": m.end(),
                                 "bucket": idx[t][k][0], "key": k, "texto": w})
                i += 1
            ln["entities"] = ents
            prev_text, prev_par = ln["text"], ln["paragraph"]


# ----------------------------------------------------------------- pipeline

def build(cfg: dict) -> dict:
    bc = cfg["bressay"]
    root = fetch(cfg)
    data_dir = resolve(cfg, "raw").parent
    out_dir = resolve(cfg, "bressay")
    page_split = {}
    for split, fname in SPLIT_FILES.items():
        for page in (root / "sets" / fname).read_text().split():
            page_split[page] = split

    lines, dropped = [], Counter()
    for png in tqdm(sorted((root / "data" / "lines").glob("*/*.png")), desc="BRESSAY linhas"):
        txt = png.with_suffix(".txt")
        if not txt.exists():
            dropped["sem_transcricao"] += 1
            continue
        page = png.parent.name
        if page not in page_split:
            dropped["fora_da_particao"] += 1
            continue
        text, why = clean(txt.read_text(encoding="utf-8").strip(), bc)
        if text is None:
            dropped[why] += 1
            continue
        parts = png.stem.split("-")  # <página>-<parágrafo>-<linha>, página = AAAA-BBB
        with Image.open(png) as im:
            width, height = im.size
        lines.append({
            "id": f"bressay_{png.stem}", "image": str(png.relative_to(data_dir)),
            "text": text, "page": page, "paragraph": int(parts[-2]), "line": int(parts[-1]),
            "split": page_split[page], "width": width, "height": height,
            "source": "bressay",
        })

    find_names(lines, resolve(cfg, "lexicon"), set(bc["name_stopwords"]))

    stats = {"linhas_mantidas": len(lines), "descartadas": dict(dropped), "por_split": {}}
    for split in SPLIT_FILES:
        rows = [ln for ln in lines if ln["split"] == split]
        (out_dir / split).mkdir(parents=True, exist_ok=True)
        with open(out_dir / split / "labels.jsonl", "w", encoding="utf-8") as f:
            for ln in rows:
                f.write(json.dumps({k: v for k, v in ln.items() if k != "split"},
                                   ensure_ascii=False) + "\n")
        ents = [e for ln in rows for e in ln["entities"]]
        stats["por_split"][split] = {
            "paginas": len({ln["page"] for ln in rows}),
            "linhas": len(rows),
            "linhas_com_nome": sum(1 for ln in rows if ln["entities"]),
            "entidades": dict(Counter(f"{e['type']}/{e['bucket']}" for e in ents)),
        }

    with open(out_dir / "nomes_para_revisao.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "tipo", "bucket", "nome", "linha", "correto(s/n)"])
        for ln in lines:
            for e in ln["entities"]:
                w.writerow([ln["id"], e["type"], e["bucket"], e["texto"], ln["text"], ""])
    write_json(out_dir / "stats.json", stats)
    print(f"  BRESSAY: {stats['linhas_mantidas']} linhas mantidas, descartadas={stats['descartadas']}")
    for split, st in stats["por_split"].items():
        print(f"    {split}: {st['linhas']} linhas, {st['linhas_com_nome']} com nome, {st['entidades']}")
    return stats
