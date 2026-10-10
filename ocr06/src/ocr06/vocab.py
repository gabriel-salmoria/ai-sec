"""Seleção do vocabulário por frequência real e reserva de nomes para validação/teste.

Regras (configs: `vocab` e `sampling`):
1. Prioridade pela população: prenomes, sobrenomes e municípios entram em ordem de
   frequência real. O corte K é a maior lista em que até o nome menos frequente aparece
   pelo menos `min_expected` vezes (esperado) no treino, dado o nº de linhas, ou a
   lista que cobre `coverage` da população, se for um número.
2. Nomes "comuns" (os primeiros `common_mass` da população) aparecem em todos os
   splits. Uma fração dos "raros" do vocabulário fica reservada só para validação ou
   só para teste: são os nomes nunca vistos no treino que a proposta exige no teste.
3. Amostragem estratificada: em cada split, a massa de comuns e raros é a mesma da
   curva suavizada (p^alpha) do vocabulário inteiro, então treino e teste seguem a
   mesma distribuição; só muda quais raros entram.
"""
from __future__ import annotations

import numpy as np

from .common import read_csv, read_json

KINDS = ("prenome", "sobrenome", "cidade")


def load_rows(lex_dir) -> dict[str, list[dict]]:
    """Linhas do léxico por tipo, ordenadas da mais para a menos frequente."""
    pren = read_csv(lex_dir / "prenomes.csv")
    sob = read_csv(lex_dir / "sobrenomes.csv")
    mun = read_csv(lex_dir / "municipios.csv")
    for r in pren + sob:
        r["w"] = float(r["freq"])
    for r in mun:
        r["w"] = float(r["pop"])
        r["key"] = r["id"]
    return {k: sorted(v, key=lambda r: -r["w"]) for k, v in
            (("prenome", pren), ("sobrenome", sob), ("cidade", mun))}


def tokens_per_line(cfg: dict, estrutura: dict) -> dict[str, float]:
    """Nº esperado de tokens reais por linha (analítico, a partir dos templates)."""
    s = cfg["sampling"]
    real = 1 - s["p_invented"]
    n_sob = sum(int(k) * v for k, v in estrutura["n_sobrenomes"].items())
    n_pren = 1 + estrutura["p_prenome_composto"]
    w = np.array([t["weight"] for t in s["templates"]], dtype=float)
    w /= w.sum()
    out = {"prenome_M": 0.0, "prenome_F": 0.0, "sobrenome": 0.0, "cidade": 0.0}
    for wt, t in zip(w, s["templates"]):
        p = t["pattern"]
        nomes = {"M": p.count("{nome_m}") + 0.5 * p.count("{nome}"),
                 "F": p.count("{nome_f}") + 0.5 * p.count("{nome}")}
        for g, c in nomes.items():
            out[f"prenome_{g}"] += wt * c * n_pren * real
        out["sobrenome"] += wt * (nomes["M"] + nomes["F"]) * n_sob * real
        out["cidade"] += wt * min(1, p.count("{cidade}") + p.count("{uf}"))
    return out


def bucket_masses(rows: list[dict], alpha: float) -> dict[str, float]:
    w = np.array([r["w"] for r in rows]) ** alpha
    tot = w.sum() or 1.0
    out: dict[str, float] = {}
    for r, x in zip(rows, w):
        out[r["bucket"]] = out.get(r["bucket"], 0.0) + x / tot
    return out


def stratified_q(rows: list[dict], alpha: float, masses: dict[str, float]) -> np.ndarray:
    """q_i = M_b * p_i^alpha / soma_{j em b} p_j^alpha (renormalizado se faltar bucket)."""
    w = np.array([r["w"] for r in rows]) ** alpha
    b = np.array([r["bucket"] for r in rows])
    q = np.zeros_like(w)
    for bucket, m in masses.items():
        sel = b == bucket
        if sel.any():
            q[sel] = m * w[sel] / w[sel].sum()
    return q / q.sum()


def _split_of(r: dict, vc: dict) -> str:
    if r["bucket"] == "comum":
        return "all"
    u = float(r["u"])
    if u < vc["heldout_test"]:
        return "test"
    if u < vc["heldout_test"] + vc["heldout_val"]:
        return "val"
    return "train"


def _gender_groups(kind: str, rows: list[dict]) -> dict[str, list[int]]:
    if kind != "prenome":
        return {"": list(range(len(rows)))}
    return {g: [i for i, r in enumerate(rows) if r["gender"] == g] for g in ("M", "F")}


def _min_expected(kind, V, splits, alpha, n_train, tpl) -> float:
    """Menor nº esperado de aparições no treino entre os nomes visíveis no treino."""
    worst = np.inf
    for g, idx in _gender_groups(kind, V).items():
        rows = [V[i] for i in idx]
        vis = [r for r, s in zip(rows, (splits[i] for i in idx)) if s in ("all", "train")]
        if not vis:
            continue
        q = stratified_q(vis, alpha, bucket_masses(rows, alpha))
        rate = tpl[f"prenome_{g}"] if kind == "prenome" else tpl[kind]
        worst = min(worst, float(q.min()) * n_train * rate)
    return worst


def select_vocab(cfg: dict, lex_dir, n_train: int) -> dict:
    vc, alpha_map = cfg["vocab"], {"prenome": cfg["sampling"]["alpha"],
                                   "sobrenome": cfg["sampling"]["alpha"],
                                   "cidade": cfg["sampling"]["alpha_cidade"]}
    rows = load_rows(lex_dir)
    tpl = tokens_per_line(cfg, read_json(lex_dir / "estrutura.json"))
    out = {"n_train": n_train, "params": vc, "tokens_por_linha": tpl}
    for kind in KINDS:
        R, alpha = rows[kind], alpha_map[kind]
        splits_all = [_split_of(r, vc) for r in R]
        w = np.array([r["w"] for r in R])
        cum = np.cumsum(w) / w.sum()
        if vc["coverage"] == "auto":
            lo, hi = 1, len(R)
            while lo < hi:  # maior K com min_expected >= alvo
                mid = (lo + hi + 1) // 2
                if _min_expected(kind, R[:mid], splits_all[:mid], alpha, n_train,
                                 tpl) >= vc["min_expected"]:
                    lo = mid
                else:
                    hi = mid - 1
            K = lo
        else:
            K = int(np.searchsorted(cum, float(vc["coverage"])) + 1)
        K = min(K, len(R))
        V, S = R[:K], splits_all[:K]
        out[kind] = {
            "K": K,
            "total_no_lexico": len(R),
            "cobertura_populacao": float(cum[K - 1]),
            "freq_minima": float(V[-1]["w"]),
            "min_esperado_treino": _min_expected(kind, V, S, alpha, n_train, tpl),
            "splits": {r["key"]: s for r, s in zip(V, S)},
        }

    # Um nome reservado (val/test) não pode aparecer no treino nem em outro papel
    # (ex.: PEDRO prenome comum e PEDRO sobrenome raro): nesse caso volta para o treino.
    pren, sob = out["prenome"]["splits"], out["sobrenome"]["splits"]
    for a, b in ((pren, sob), (sob, pren)):
        for k, s in a.items():
            if s in ("val", "test") and b.get(k) in ("all", "train"):
                a[k] = "train"
    for kind in KINDS:
        sp = out[kind]["splits"].values()
        out[kind]["por_split"] = {s: sum(1 for x in sp if x == s)
                                  for s in ("all", "train", "val", "test")}
    return out


def visible(vocab: dict, kind: str, split: str) -> set[str]:
    """Chaves sorteáveis num split: comuns ('all') + as reservadas para ele."""
    return {k for k, s in vocab[kind]["splits"].items() if s in ("all", split)}
