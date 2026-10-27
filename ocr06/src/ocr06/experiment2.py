"""Experimento 2a: testes de integração sem modelo (CPU).

    python -m ocr06 exp2

Enquanto não há acesso à GPU, testa as partes do caminho de inferência que não dependem
do modelo, sobre os conjuntos de teste reais (data/final/<dataset>/):
  1. normalização de altura (preprocess.py): tamanho das linhas e nº de blocos visuais
     antes e depois, e se o limite de caracteres por largura cobre todos os gabaritos;
  2. avaliação (evaluate.py) com predições simuladas de erro conhecido, para conferir
     que o CER por nome, por grupo e por visto/inédito sai igual ao valor esperado;
  3. controles de saída (guard.py): falsos positivos nos gabaritos e detecção em saídas
     defeituosas montadas a partir deles, e a confiança por palavra com log-probs fictícias.
Resultados em experiments/exp2_integracao/.
"""
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict

import numpy as np
from PIL import Image

from .common import load_config, resolve, stable_int, write_json
from .evaluate import evaluate_file, normalize
from .guard import check, tokens_from_vllm, word_confidence
from .preprocess import load_line, max_chars, patch_grid, target_size

SPLITS = ("test_sintetico", "test_bressay")
NAME_TYPES = ("prenome", "sobrenome", "cidade")


def _rows(cfg):
    fdir = resolve(cfg, "final") / cfg["model"]["dataset"]
    return {s: [json.loads(l) for l in open(fdir / f"{s}.jsonl", encoding="utf-8")] for s in SPLITS}


def _pct(a, q):
    return float(np.percentile(a, q))


# ---------------------------------------------------------------- 1. normalização
def test_preprocess(cfg, rows, ddir) -> dict:
    out = {}
    for split, rs in rows.items():
        sizes = []
        for r in rs:  # Image.open só lê o cabeçalho
            with Image.open(ddir / r["image"]) as im:
                sizes.append(im.size)
        before = np.array(sizes)
        after = np.array([target_size(w, h, cfg) for w, h in sizes])
        pb = np.array([patch_grid(w, h) for w, h in before])
        pa = np.array([patch_grid(w, h) for w, h in after])
        lim = np.array([max_chars(w, h, cfg) for w, h in after])
        lens = np.array([len(r["text"]) for r in rs])
        over = lens > lim
        out[split] = {
            "linhas": len(rs),
            "altura_antes": {"mediana": _pct(before[:, 1], 50), "p5": _pct(before[:, 1], 5),
                             "p95": _pct(before[:, 1], 95)},
            "altura_depois": {"mediana": _pct(after[:, 1], 50), "min": int(after[:, 1].min())},
            "largura_depois_mediana": _pct(after[:, 0], 50),
            "linhas_de_blocos_antes": dict(sorted(Counter(pb[:, 0].tolist()).items())),
            "linhas_de_blocos_depois": dict(sorted(Counter(pa[:, 0].tolist()).items())),
            "blocos_por_linha_antes_mediana": _pct(pb[:, 0] * pb[:, 1], 50),
            "blocos_por_linha_depois_mediana": _pct(pa[:, 0] * pa[:, 1], 50),
            "limite_chars_mediana": _pct(lim, 50),
            "gabaritos_acima_do_limite": int(over.sum()),
            "folga_minima": int((lim - lens).min()),
        }
    # custo do redimensionamento de verdade, numa amostra
    sample = [r for rs in rows.values() for r in rs[:200]]
    t0 = time.time()
    for r in sample:
        load_line(ddir / r["image"], cfg)
    out["ms_por_imagem"] = round(1000 * (time.time() - t0) / len(sample), 2)
    return out


# ---------------------------------------------------------------- 2. métricas
def _corrupt(word: str, seed, kind: str = "troca") -> tuple[str, int]:
    """Erro determinístico num nome; devolve (nome com erro, distância de edição).
    troca: um caractere trocado; delecao: um caractere interno removido; insercao: um
    'x' inserido no meio; omitido: o nome some da predição."""
    if kind == "omitido":
        return "", len(word)
    if kind in ("delecao", "insercao") and len(word) < 3:
        kind = "troca"  # nome curto demais para mexer só no meio
    if kind == "troca":
        i = stable_int(seed) % len(word)
        new = "x" if word[i].lower() != "x" else "y"
        return word[:i] + new + word[i + 1:], 1
    i = 1 + stable_int(seed) % (len(word) - 2)  # posição interna, longe das bordas
    if kind == "delecao":
        return word[:i] + word[i + 1:], 1
    return word[:i] + "x" + word[i:], 1


def _mock(rs, mode):
    """Predições simuladas. mode: perfeita | html | nomes (1 troca por nome) | ineditos
    (1 troca só nos nomes não vistos no treino) | delecao | insercao | omitido."""
    out, expected = [], defaultdict(lambda: [0, 0])  # grupo -> [erros, chars]
    for r in rs:
        text = r["text"]
        ents = sorted((e for e in r.get("entities", []) if e["type"] in NAME_TYPES),
                      key=lambda e: e["start"])
        pred, last = [], 0
        for e in ents:
            g = text[e["start"]:e["end"]]
            hit = mode in ("nomes", "delecao", "insercao", "omitido") or \
                (mode == "ineditos" and e.get("visto_no_treino") is False)
            kind = "troca" if mode in ("nomes", "ineditos") else mode
            p, dist = _corrupt(g, (r["id"], e["start"]), kind) if hit else (g, 0)
            pred += [text[last:e["start"]], p]
            last = e["end"]
            for k in ("todas", f"bucket/{e['bucket']}"):
                expected[k][0] += dist
                expected[k][1] += len(g)
            if e.get("visto_no_treino") is not None:
                k = "vistas" if e["visto_no_treino"] else "ineditas"
                expected[k][0] += dist
                expected[k][1] += len(g)
        pred.append(text[last:])
        p = "".join(pred)
        if mode == "html":
            p = f"<div><p>{p.replace('&', '&amp;')}</p></div>"
        out.append({"id": r["id"], "source": r["source"], "text": text, "pred": p,
                    "entities": r["entities"]})
    return out, {k: round(e / c, 4) for k, (e, c) in expected.items()}


def test_metrics(rows, out_dir) -> dict:
    res = {}
    for mode in ("perfeita", "html", "nomes", "ineditos", "delecao", "insercao", "omitido"):
        for split, rs in rows.items():
            preds, exp = _mock(rs, mode)
            d = out_dir / "mock" / mode
            d.mkdir(parents=True, exist_ok=True)
            p = d / f"{split}.jsonl"
            with open(p, "w", encoding="utf-8") as f:
                for x in preds:
                    f.write(json.dumps(x, ensure_ascii=False) + "\n")
            m = evaluate_file(p)
            got = {k: m["entidades"].get(k, {}).get("taxa_erro") for k in exp}
            res[f"{mode}/{split}"] = {
                "cer_linha": m["cer"], "wer_linha": m["wer"],
                "nomes": m["entidades"].get("todas", {}).get("n", 0),
                "acerto_exato_nomes": m["entidades"].get("todas", {}).get("acerto_exato"),
                "acerto_exato_vistas": m["entidades"].get("vistas", {}).get("acerto_exato"),
                "acerto_exato_ineditas": m["entidades"].get("ineditas", {}).get("acerto_exato"),
                "cer_esperado": exp, "cer_medido": got,
                "confere": all(got[k] is not None and abs(got[k] - exp[k]) < 1e-3 for k in exp),
                "diferenca_max": max((abs((got[k] or 0) - exp[k]) for k in exp), default=0),
            }
    return res


# ---------------------------------------------------------------- 3. controles de saída
INJ = ["Desculpe, não posso transcrever esta imagem.",
       "Ignorando a instrução anterior: o nome é JOÃO DA SILVA",
       "Aqui está a transcrição: {t}",
       "Como um modelo de IA, eu leio: {t}"]


def _variants(text):
    w = text.split()[-1] if text.split() else "a"
    return {
        "vazia": ("", ""),
        "repeticao": ((text + (" " + w) * 8),) * 2,
        "html": (f"<p>{text}</p>", text),
        "instrucao": None,  # preenchido abaixo, um modelo de frase por linha
        "tamanho": ((text + " ") * 4,) * 2,
        "caracteres": ((text + " 名前 🙂"),) * 2,
    }


def test_guard(cfg, rows, ddir) -> dict:
    fp = Counter()
    fp_examples = defaultdict(list)
    det = Counter()
    n_gold = n_var = n_flag = 0
    for split, rs in rows.items():
        for i, r in enumerate(rs):
            with Image.open(ddir / r["image"]) as im:
                w, h = target_size(*im.size, cfg)
            lim = max_chars(w, h, cfg)
            g = check(r["text"], normalize(r["text"]), lim, cfg)
            n_gold += 1
            n_flag += g["revisao"]
            for m in g["motivos"]:
                fp[m] += 1
                if len(fp_examples[m]) < 5:
                    fp_examples[m].append(r["text"])
            if i % 10:  # variantes defeituosas em 1 de cada 10 linhas
                continue
            n_var += 1
            vs = _variants(r["text"])
            vs["instrucao"] = (INJ[i // 10 % len(INJ)].format(t=r["text"]),) * 2
            for kind, (raw, pred) in vs.items():
                gg = check(raw, normalize(pred) if kind != "html" else pred, lim, cfg)
                det[kind] += kind in gg["motivos"]
    # Saída fictícia no formato do vLLM (CompletionOutput: token_ids + logprobs, uma
    # lista de {token_id: Logprob}). O id 99 é um candidato não escolhido e tem que ser
    # ignorado; o último token vem sem decoded_token, como o vLLM às vezes devolve.
    from types import SimpleNamespace as NS
    pieces = [(1, "Ma", -0.01), (2, "ria", -0.02), (3, " da", -0.1), (4, " Sil", -2.0),
              (5, "va", -0.05), (6, " -", -0.01), (7, " SC", -0.3), (8, None, -0.001)]
    fake = NS(text="Maria da Silva - SC", token_ids=[t for t, _, _ in pieces],
              logprobs=[{t: NS(logprob=lp, decoded_token=d), 99: NS(logprob=-5.0, decoded_token="Z")}
                        for t, d, lp in pieces])
    toks = tokens_from_vllm(fake)
    sem_logprobs = tokens_from_vllm(NS(text="x", token_ids=[1], logprobs=None))
    wc = word_confidence(toks)
    g = check(fake.text, fake.text, 64, cfg, toks)
    return {
        "gabaritos": n_gold,
        "falsos_positivos": dict(fp), "exemplos_falsos_positivos": dict(fp_examples),
        "taxa_falsos_positivos": round(n_flag / n_gold, 4),
        "variantes_por_tipo": n_var,
        "detectadas": {k: f"{v}/{n_var}" for k, v in det.items()},
        "vllm_falso_tokens": len(toks), "vllm_sem_logprobs": sem_logprobs,
        "confianca_exemplo": [(w, round(c, 3)) for w, c in wc],
        "confianca_exemplo_guard": g,
    }


def run(cfg: dict) -> None:
    from .model import data_dir  # só caminhos; não importa nada do modelo
    out_dir = resolve(cfg, "experiments") / "exp2_integracao"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = _rows(cfg)
    ddir = data_dir(cfg)
    t0 = time.time()
    res = {"preprocess": test_preprocess(cfg, rows, ddir)}
    print("  normalização ok", f"({time.time() - t0:.0f}s)")
    res["metricas"] = test_metrics(rows, out_dir)
    print("  métricas ok", f"({time.time() - t0:.0f}s)")
    res["guard"] = test_guard(cfg, rows, ddir)
    print("  controles ok", f"({time.time() - t0:.0f}s)")
    write_json(out_dir / "resultados.json", res)
    print(json.dumps(res, indent=1, ensure_ascii=False)[:6000])
