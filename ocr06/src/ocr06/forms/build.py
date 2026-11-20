"""Gera as páginas locais de formulários.

    python -m ocr06.forms.build --name forms_amostra --count 20
    python -m ocr06.forms.build --name forms_v1 --count 1000 --hands font:0.6,graves:0.4

Três passos: (1) cada página sorteia modelo, nível, partição, mão e o registro re-sorteado;
(2) os textos das páginas com mão neural são renderizados em lote pelo gerador (no
ambiente dele, `scripts/hw/render_<gerador>.py`); (3) as páginas são compostas em paralelo.
Saída em data/pages/<name>/: images/<id>.jpg e pages.jsonl. Retoma se interrompido.

Partições: 10% das páginas são de teste, com nomes da partição de teste do vocabulário,
as 17 fontes reservadas e esqueletos do OCRSD que o treino não usa.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from multiprocessing import Pool
from pathlib import Path

import cv2
import numpy as np

from ..common import load_config
from ..fonts import fonts_for_split
from .compose import make_page
from .hands import FontHand, NeuralHand, TypeHand
from .records import BRESSAY_UNSEEN, key_of, neural_safe, ocrsd_skeletons, remap_record

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_W = {"certidao_casamento": 0.19, "certidao_casamento_cnj": 0.19, "certidao_nascimento_cnj": 0.19,
              "certidao_obito": 0.19, "dnv": 0.24}
LEVEL_W = {1: 0.25, 2: 0.30, 3: 0.30, 4: 0.15}
TYPE_FONTS = ["CourierPrime.ttf", "SpecialElite.ttf"]
# Letra de gente: sem caligrafia ornamental (que ninguém usa num formulário), sem marcador
# grosso e sem fontes de vitrine. Inclui as cursivas escolares (Playwrite).
KEEP_FONTS = {"Caveat", "Kalam", "Handlee", "LaBelleAurore", "CedarvilleCursive", "NothingYouCouldDo",
              "ReenieBeanie", "HomemadeApple", "CoveredByYourGrace", "SueEllenFrancisco", "JustAnotherHand", "JustMeAgainDownHere",
              "AnnieUseYourTelescope", "WaitingfortheSunrise", "TheGirlNextDoor", 
              "DawningofaNewDay", "Mynerve",
              "GrapeNuts", "BadScript", "Zeyada", "GiveYouGlory", "MarckScript", "PlaywriteBR", "PlaywritePT", "PlaywriteES", "PlaywriteITTrad",
              "PlaywriteFRTrad", "PlaywriteUSTrad", "PlaywriteAR", "PlaywriteMX", "PlaywriteDEGrund"}
# Geradores neurais (cada um no seu ambiente). Nenhum escreve acento/ç: só recebem textos
# sem esses caracteres (o resto da página sai datilografado). Estilos de teste reservados:
# sjvasquez 10-11 (as mesmas mãos do OCRSD de teste) e os últimos 20 escritores do IAM.
GENERATORS = {
    "graves": {"python": ".venv-hw-graves/bin/python", "script": "scripts/hw/render_graves.py",
               "styles": {"train": list(range(10)), "test": [10, 11]}, "safe_only": True},
    "vatrpp": {"python": ".venv-hw-vatrpp/bin/python", "script": "scripts/hw/render_vatrpp.py",
               "styles": {"train": list(range(141)), "test": list(range(141, 161))}, "safe_only": True},
}
GRAVES_BIAS = {1: 0.6, 2: 0.45, 3: 0.35, 4: 0.25}


def _u(s: str) -> float:
    return int(hashlib.sha1(s.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def plan(n: int, seed: int, test_frac: float, hands: dict[str, float]) -> list[dict]:
    rng = np.random.default_rng(seed)
    ts, tw = list(TEMPLATE_W), np.array(list(TEMPLATE_W.values()))
    lv, lw = list(LEVEL_W), np.array(list(LEVEL_W.values()))
    hs, hw = list(hands), np.array(list(hands.values()))
    return [{"i": i, "template": ts[rng.choice(len(ts), p=tw / tw.sum())],
             "level": int(lv[rng.choice(len(lv), p=lw / lw.sum())]),
             "split": "test" if rng.random() < test_frac else "train",
             "hand": hs[rng.choice(len(hs), p=hw / hw.sum())], "seed": int(seed * 1_000_003 + i)}
            for i in range(n)]


def prepare(job: dict, cfg_path: str) -> dict:
    """Sorteios da página (registro, fonte ou estilo neural, máquina de escrever)."""
    cfg = load_config(cfg_path)
    rng = np.random.default_rng(job["seed"])
    sk = [s for s in ocrsd_skeletons(job["template"]) if (_u(s["_id"]) < 0.15) == (job["split"] == "test")]
    skel = sk[int(rng.integers(len(sk)))]
    neural = job["hand"] != "font"
    p = dict(job)
    if neural:
        g = GENERATORS[job["hand"]]
        st = g["styles"]["test" if job["split"] == "test" else "train"]
        p["style"] = st[int(rng.integers(len(st)))]
        p["bias"] = round(float(np.clip(GRAVES_BIAS[job["level"]] + rng.normal(0, 0.06), 0.15, 1.2)), 2)
    else:
        fonts = [f for f in fonts_for_split(cfg, "test" if job["split"] == "test" else "train")
                 if Path(f).stem in KEEP_FONTS]
        p["font"] = fonts[int(rng.integers(len(fonts)))]
    p["typefont"] = str(ROOT / "data" / "fonts" / "typewriter" / TYPE_FONTS[int(rng.integers(2))])
    safe_only = neural and GENERATORS[job["hand"]]["safe_only"]
    p["record"] = remap_record(skel, job["split"], neural=safe_only, rng=rng)
    return p


def neural_texts(p: dict) -> list[str]:
    """Textos que a mão neural escreve nesta página (o resto vai datilografado)."""
    safe_only = GENERATORS[p["hand"]]["safe_only"]
    out = set()
    for f in p["record"]["fields"]:
        els = f.get("elements") or []
        if els and any("index" in e for e in els):
            out.update(e["value"] for e in els if e.get("value"))
        elif els:
            continue
        elif not f.get("blank"):
            t = " ".join(f["value"].split())
            # o modelo de Graves se perde em sequências longas de dígitos (matrícula, CNS):
            # esses campos ficam em branco nas páginas dele
            if p["hand"] == "graves" and sum(c.isdigit() for c in t) > 10:
                continue
            if t and (not safe_only or neural_safe(t)):
                out.add(t)
    return sorted(out)


def render_neural(preps: list[dict], cache_dir: Path) -> dict[tuple, str]:
    """Roda cada gerador uma vez para todos os textos das páginas que o usam."""
    paths = {}
    for gen in sorted({p["hand"] for p in preps if p["hand"] != "font"}):
        g = GENERATORS[gen]
        jobs, keys = [], {}
        for p in preps:
            if p["hand"] != gen:
                continue
            for t in neural_texts(p):
                # Graves com bias baixo embaralha dígitos (ninguém recupera um dígito pelo
                # contexto): números sempre com a mão mais firme.
                digits = sum(c.isdigit() for c in t) >= max(len(t) * 0.5, 1)
                bias = max(p["bias"], 0.9) if digits else p["bias"]
                jid = hashlib.sha1(f"{gen}|{t}|{p['style']}|{bias}".encode()).hexdigest()[:16]
                keys[(p["i"], t)] = jid
                if not (cache_dir / f"{jid}.png").exists():
                    jobs.append({"id": jid, "text": t, "style": p["style"],
                                 "params": {"bias": bias, "seed": int(p["seed"] % 2**31)}})
        uniq = {j["id"]: j for j in jobs}
        if uniq:
            cache_dir.mkdir(parents=True, exist_ok=True)
            jf = cache_dir / f"jobs_{gen}.jsonl"
            jf.write_text("".join(json.dumps(j, ensure_ascii=False) + "\n" for j in uniq.values()), encoding="utf-8")
            print(f"  {gen}: {len(uniq)} textos para renderizar")
            subprocess.run([str(ROOT / g["python"]), str(ROOT / g["script"]), "--jobs", str(jf),
                            "--out", str(cache_dir)], check=True)
        for k, jid in keys.items():
            meta = cache_dir / f"{jid}.json"
            ok = meta.exists() and json.loads(meta.read_text()).get("ok", False)
            if ok:
                paths[k] = str(cache_dir / f"{jid}.png")
    return paths


def compose(args) -> dict:
    p, name, cfg_path, cache = args
    cfg = load_config(cfg_path)
    rng = np.random.default_rng(p["seed"] + 1)
    if p["hand"] == "font":
        family = Path(p["font"]).stem
        script = family in {s.replace(" ", "") for s in cfg["fonts"]["script"]}
        hand = FontHand(p["font"], script, cfg["render"], p["level"], rng)
    else:
        hand = NeuralHand(p["hand"], cache, p["level"], rng, p.get("style"), p.get("bias"))
    typer = TypeHand(p["typefont"], rng)
    tpl = str(ROOT / "data" / "forms" / p["template"] / "template.png")
    img, fields, meta = make_page(tpl, p["template"], p["record"], hand, typer, p["level"], p["seed"])
    pid = f"{name}_{p['i']:05d}"
    cv2.imwrite(str(ROOT / "data" / "pages" / name / "images" / f"{pid}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return {"id": pid, "image": f"pages/{name}/images/{pid}.jpg", "template": p["template"],
            "split": p["split"], "level": p["level"], "skeleton": p["record"]["skeleton"],
            "writer": hand.desc, "remap": p["record"]["remap"], **meta, "fields": fields}


def check_names(rows: list[dict]) -> list[str]:
    """Nenhum nome inédito do BRESSAY pode aparecer numa página gerada."""
    blocked = BRESSAY_UNSEEN["prenome"] | BRESSAY_UNSEEN["sobrenome"]
    return [f"{r['id']}:{f['field_id']}:{tok}" for r in rows for f in r["fields"]
            for tok in f["text"].replace(";", " ").replace(",", " ").split() if key_of(tok) in blocked]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--count", type=int, required=True)
    ap.add_argument("--seed", type=int, default=20261115)
    ap.add_argument("--test-frac", type=float, default=0.10)
    ap.add_argument("--hands", default="font:0.3,vatrpp:0.5,graves:0.2", help="ex.: font:0.6,graves:0.4")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--level", type=int, help="força um nível (amostras)")
    ap.add_argument("--only-test", action="store_true", help="as páginas novas são todas de teste")
    ap.add_argument("--config", default=str(ROOT / "configs" / "default.yaml"))
    a = ap.parse_args()
    hands = {k: float(v) for k, v in (x.split(":") for x in a.hands.split(","))}
    out_dir = ROOT / "data" / "pages" / a.name
    (out_dir / "images").mkdir(parents=True, exist_ok=True)
    manifest = out_dir / "pages.jsonl"
    done = {json.loads(l)["id"] for l in open(manifest, encoding="utf-8")} if manifest.exists() else set()
    jobs = plan(a.count, a.seed, a.test_frac, hands)
    if a.level:
        for j in jobs:
            j["level"] = a.level
    jobs = [j for j in jobs if f"{a.name}_{j['i']:05d}" not in done]
    if a.only_test:
        for j in jobs:
            j["split"] = "test"
    with Pool(a.workers) as pool:
        preps = pool.starmap(prepare, [(j, a.config) for j in jobs])
    found = render_neural(preps, ROOT / "data" / "hw_cache") if any(p["hand"] != "font" for p in preps) else {}
    args = [(p, a.name, a.config, {t: v for (i, t), v in found.items() if i == p["i"]}) for p in preps]
    with Pool(a.workers) as pool, open(manifest, "a", encoding="utf-8") as fh:
        for r in pool.imap_unordered(compose, args):
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            fh.flush()
    allrows = [json.loads(l) for l in open(manifest, encoding="utf-8")]
    bad = check_names(allrows)
    print(f"{len(allrows)} páginas em {out_dir}; nomes bloqueados encontrados: {len(bad)} {bad[:5]}")


if __name__ == "__main__":
    main()
