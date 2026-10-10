"""Experimento 1: validação do pipeline de dados (roda só em CPU).

A. Vocabulário por orçamento: para cada tamanho de treino, quantos nomes entram
   (por ordem de frequência real), quanto da população cobrem e quantas vezes o
   nome menos frequente aparece.
B. Efeito da temperatura alpha (com o orçamento padrão): fração de comuns vs raros,
   massa do top-10, tipos efetivos e aderência do amostrador ao alvo.
C. Linhas completas: templates, buckets e prova de que os nomes reservados para o
   teste não aparecem no treino.
D. Custo e qualidade visual: vazão, disco, rejeições do controle de contraste,
   folha de contato e planilha de inspeção manual.
E. BRESSAY (se já processado): linhas mantidas/descartadas, linhas com nome e
   tamanho das imagens reais vs sintéticas.

Saídas em experiments/exp1/.
"""
from __future__ import annotations

import csv
import json
import shutil
from collections import Counter
from pathlib import Path

import cv2
import matplotlib
import matplotlib.ticker
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .common import read_json, resolve, write_json
from .generate import generate_split, n_workers
from .sampler import NameSampler
from .vocab import KINDS as VOCAB_KINDS, select_vocab, visible

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# Paleta categórica validada (slots 1-3), texto e grade discretos.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]
TEXT, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def br(x: float, nd: int = 1) -> str:
    """Formata número no padrão brasileiro (1.234,5)."""
    return f"{x:,.{nd}f}".replace(",", "_").replace(".", ",").replace("_", ".")


KINDS = {"prenome": "Prenomes", "sobrenome": "Sobrenomes", "cidade": "Municípios"}


def _with_alpha(cfg: dict, alpha: float) -> dict:
    c = {**cfg, "sampling": {**cfg["sampling"], "alpha": alpha, "alpha_cidade": alpha}}
    return c


def _train_q(cfg: dict, lex_dir, vocab: dict) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """(q, buckets) do treino por tipo; prenomes juntam M e F (cada gênero = metade)."""
    s = NameSampler(lex_dir, "train", cfg["sampling"], vocab)
    out = {}
    pm, pf = s.prenomes["M"], s.prenomes["F"]
    out["prenome"] = (np.concatenate([0.5 * pm.q, 0.5 * pf.q]),
                      np.array([r["bucket"] for r in pm.rows + pf.rows]))
    for kind, pool in (("sobrenome", s.sobrenomes), ("cidade", s.municipios)):
        out[kind] = (pool.q, np.array([r["bucket"] for r in pool.rows]))
    return out


def vocab_table(cfg: dict, lex_dir) -> list[dict]:
    rows = []
    for budget in cfg["experiment1"]["budgets"]:
        v = select_vocab(cfg, lex_dir, budget)
        for kind in VOCAB_KINDS:
            x = v[kind]
            rows.append({"imagens_treino": budget, "tipo": kind, "K": x["K"],
                         "total_no_lexico": x["total_no_lexico"],
                         "cobertura_populacao": x["cobertura_populacao"],
                         "freq_minima": x["freq_minima"],
                         "min_esperado_treino": x["min_esperado_treino"],
                         "reservados_val": x["por_split"]["val"],
                         "reservados_teste": x["por_split"]["test"]})
    return rows


def sampling_stats(cfg: dict, lex_dir) -> tuple[list[dict], dict]:
    ec = cfg["experiment1"]
    n_train = cfg["generate"]["n"]["train"]
    rows, curves = [], {}
    for alpha in ec["alphas"]:
        c = _with_alpha(cfg, alpha)
        vocab = select_vocab(c, lex_dir, n_train)
        rng = np.random.default_rng(cfg["seed"])
        for kind, (q, buckets) in _train_q(c, lex_dir, vocab).items():
            cum = np.cumsum(q)
            idx = np.minimum(np.searchsorted(cum, rng.random(ec["n_draws"]) * cum[-1],
                                             side="right"), len(q) - 1)
            emp = np.bincount(idx, minlength=len(q)) / ec["n_draws"]
            order = np.sort(q)[::-1]
            rows.append({
                "alpha": alpha, "tipo": kind, "K": vocab[kind]["K"],
                "cobertura_populacao": vocab[kind]["cobertura_populacao"],
                "frac_comum_alvo": float(q[buckets == "comum"].sum()),
                "frac_comum_empirica": float(emp[buckets == "comum"].sum()),
                "frac_raro_empirica": float(emp[buckets == "raro"].sum()),
                "massa_top10": float(order[:10].sum()),
                "tipos_efetivos": float(np.exp(-(q[q > 0] * np.log(q[q > 0])).sum())),
                # Aderência do amostrador ao alvo q: |fração comum sorteada - fração comum em q|.
                "erro_abs_frac_comum": float(abs(emp[buckets == "comum"].sum()
                                                 - q[buckets == "comum"].sum())),
            })
            curves[(alpha, kind)] = np.cumsum(order)
    return rows, curves


def plot_curves(curves: dict, alphas: list[float], out_dir) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.2), sharey=True)
    for ax, (kind, title) in zip(axes, KINDS.items()):
        for color, alpha in zip(SERIES, alphas):
            c = curves[(alpha, kind)]
            ranks = np.arange(1, len(c) + 1)
            label = f"α = {br(alpha, 1)}" + (" (real)" if alpha == 1 else "")
            ax.plot(ranks, c, color=color, lw=2, label=label)
        ax.set_xscale("log")
        ax.set_title(title, color=TEXT, fontsize=10, loc="left")
        ax.set_xlabel("posição no ranking de frequência", color=MUTED, fontsize=8)
        ax.grid(True, color=GRID, lw=0.6)
        ax.tick_params(colors=MUTED, labelsize=8)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(GRID)
    axes[0].set_ylabel("massa de probabilidade acumulada", color=MUTED, fontsize=8)
    axes[0].set_ylim(0, 1.01)
    axes[0].yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: br(v, 1)))
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=len(alphas), frameon=False,
               fontsize=8, bbox_to_anchor=(0.5, 1.02))
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(out_dir / "massa_acumulada.pdf")
    fig.savefig(out_dir / "massa_acumulada.png", dpi=200)
    plt.close(fig)


def line_stats(cfg: dict, lex_dir, vocab: dict, n: int = 20000) -> dict:
    out, keys = {}, {}
    for split in ("train", "test"):
        smp = NameSampler(lex_dir, split, cfg["sampling"], vocab)
        rng = np.random.default_rng(cfg["seed"] + (split == "test"))
        samples = [smp.compose(rng, cfg["sampling"]["templates"]) for _ in range(n)]
        ents = [e for x in samples for e in x["entities"] if e["type"] in VOCAB_KINDS]
        keys[split] = {(e["type"], e["key"]) for e in ents}
        by_type = Counter((e["type"], e["bucket"]) for e in ents)
        out[split] = {
            "linhas": n,
            "templates": dict(Counter(x["template"] for x in samples)),
            "comprimento_medio": float(np.mean([len(x["text"]) for x in samples])),
            "comprimento_max": int(max(len(x["text"]) for x in samples)),
            "tokens_por_tipo_e_bucket": {f"{t}/{b}": c for (t, b), c in sorted(by_type.items())},
            "exemplos": [x["text"] for x in samples[:15]],
        }
    # Nomes reservados para o teste: nem sorteáveis no treino, nem sorteados nele.
    reserved = {(k, key) for k in VOCAB_KINDS
                for key, s in vocab[k]["splits"].items() if s == "test"}
    train_visible = {(k, key) for k in VOCAB_KINDS for key in visible(vocab, k, "train")}
    out["reservados_teste"] = len(reserved)
    out["reservados_sorteaveis_no_treino"] = len(reserved & train_visible)
    out["reservados_sorteados_no_teste"] = len(reserved & keys["test"])
    out["reservados_sorteados_no_treino"] = len(reserved & keys["train"])
    return out


def contact_sheet(split_dir, n: int, out_path) -> None:
    labels = [json.loads(line) for line in open(split_dir / "labels.jsonl", encoding="utf-8")][:n]
    font = ImageFont.truetype(str(Path(matplotlib.get_data_path()) / "fonts/ttf/DejaVuSans.ttf"), 13)
    tiles = []
    for s in labels:
        img = Image.open(split_dir / s["image"]).convert("RGB")
        img.thumbnail((560, 80))
        tile = Image.new("RGB", (580, img.height + 26), "white")
        tile.paste(img, (10, 4))
        ImageDraw.Draw(tile).text((10, img.height + 6),
                                  f"{s['text']}   [{s['font']}, {s['degrade']}]",
                                  fill=MUTED, font=font)
        tiles.append(tile)
    cols = 2
    rows = (len(tiles) + cols - 1) // cols
    h = max(t.height for t in tiles)
    sheet = Image.new("RGB", (580 * cols, h * rows), "white")
    for k, t in enumerate(tiles):
        sheet.paste(t, ((k % cols) * 580, (k // cols) * h))
    sheet.save(out_path)


def latex_table(rows: list[dict], out_path) -> None:
    lines = [
        r"\begin{tabular}{@{}llrrrr@{}}", r"\toprule",
        r"Tipo & $\alpha$ & \% comum & \% raro & Top-10 & Tipos efetivos \\", r"\midrule",
    ]
    for kind, title in KINDS.items():
        for r in [r for r in rows if r["tipo"] == kind]:
            lines.append(f"{title} & {br(r['alpha'])} & {br(100 * r['frac_comum_empirica'])} & "
                         f"{br(100 * r['frac_raro_empirica'])} & {br(100 * r['massa_top10'])}\\% & "
                         f"{br(r['tipos_efetivos'], 0)} \\\\")
        lines.append(r"\midrule" if kind != "cidade" else r"\bottomrule")
    lines.append(r"\end{tabular}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def vocab_latex(rows: list[dict], out_path) -> None:
    lines = [r"\begin{tabular}{@{}rlrrrr@{}}", r"\toprule",
             r"Imagens & Tipo & Nomes ($K$) & Cobertura & Freq. mín. & Aparições mín. \\",
             r"\midrule"]
    budgets = sorted({r["imagens_treino"] for r in rows})
    for i, bgt in enumerate(budgets):
        for r in [r for r in rows if r["imagens_treino"] == bgt]:
            lines.append(f"{br(bgt, 0)} & {KINDS[r['tipo']]} & {br(r['K'], 0)} & "
                         f"{br(100 * r['cobertura_populacao'])}\\% & {br(r['freq_minima'], 0)} & "
                         f"{br(r['min_esperado_treino'])} \\\\")
        lines.append(r"\midrule" if i < len(budgets) - 1 else r"\bottomrule")
    lines.append(r"\end{tabular}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def bressay_stats(cfg: dict, gen: dict) -> dict | None:
    st_path = resolve(cfg, "bressay") / "stats.json"
    if not st_path.exists():
        return None
    st = read_json(st_path)
    hs, ws = [], []
    with open(resolve(cfg, "bressay") / "train" / "labels.jsonl", encoding="utf-8") as f:
        for line in f:
            s = json.loads(line)
            hs.append(s["height"])
            ws.append(s["width"])
    st["altura_media"] = float(np.mean(hs))
    st["largura_media"] = float(np.mean(ws))
    st["sintetico_altura_media"] = gen["altura_media"]
    st["sintetico_largura_media"] = gen["largura_media"]
    return st


def run(cfg: dict) -> None:
    lex_dir = resolve(cfg, "lexicon")
    out_dir = resolve(cfg, "experiments") / "exp1"
    out_dir.mkdir(parents=True, exist_ok=True)
    ec = cfg["experiment1"]
    workers = n_workers(cfg)

    print("[A] Vocabulário por orçamento de imagens")
    vrows = vocab_table(cfg, lex_dir)
    vocab_latex(vrows, out_dir / "tabela_vocabulario.tex")

    print("[B] Efeito da temperatura")
    rows, curves = sampling_stats(cfg, lex_dir)
    plot_curves(curves, ec["alphas"], out_dir)
    latex_table(rows, out_dir / "tabela_amostragem.tex")

    print("[C] Linhas completas e nomes reservados para o teste")
    vocab = select_vocab(cfg, lex_dir, cfg["generate"]["n"]["train"])
    lines = line_stats(cfg, lex_dir, vocab)

    print("[D] Geração de imagens (vazão, disco, contraste)")
    gen_root = resolve(cfg, "synthetic") / "exp1"
    img_dir = gen_root / "train"
    if img_dir.exists():
        shutil.rmtree(img_dir)
    vocab_path = gen_root / "vocab.json"
    write_json(vocab_path, vocab)
    gen = generate_split(cfg, "train", ec["n_images"], img_dir, workers, vocab_path)
    gen["bytes_por_imagem"] = gen["bytes"] / gen["n"]
    gen["imagens_por_segundo_por_worker"] = gen["imagens_por_segundo"] / workers
    sizes = [cv2.imread(str(p)).shape[:2] for p in sorted((img_dir / "images").iterdir())]
    gen["altura_media"] = float(np.mean([h for h, _ in sizes]))
    gen["largura_media"] = float(np.mean([w for _, w in sizes]))
    contact_sheet(img_dir, ec["contact_sheet"], out_dir / "folha_de_contato.png")

    with open(out_dir / "inspecao_manual.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "imagem", "texto", "fonte", "degradacao",
                    "legivel(s/n)", "texto_confere(s/n)", "observacao"])
        for line in open(img_dir / "labels.jsonl", encoding="utf-8"):
            s = json.loads(line)
            w.writerow([s["id"], str((img_dir / s["image"]).relative_to(resolve(cfg, "raw").parent)),
                        s["text"], s["font"], s["degrade"], "", "", ""])

    print("[E] BRESSAY")
    bre = bressay_stats(cfg, gen)

    write_json(out_dir / "resultados.json", {
        "config": {k: cfg[k] for k in ("seed", "vocab", "sampling", "experiment1")},
        "vocabulario": vrows, "amostragem": rows, "linhas": lines, "geracao": gen,
        "bressay": bre,
    })
    print(f"  resultados em {out_dir}")
    for r in vrows:
        print(f"  {r['imagens_treino']:>6} imgs {r['tipo']:<10} K={r['K']:<6} "
              f"cobertura={r['cobertura_populacao']:.3f} freq_min={r['freq_minima']:.0f} "
              f"min_esperado={r['min_esperado_treino']:.1f}")
    for r in rows:
        print(f"  α={r['alpha']:<4} {r['tipo']:<10} K={r['K']:<6} comum={r['frac_comum_empirica']:.3f} "
              f"top10={r['massa_top10']:.3f} erro_alvo={r['erro_abs_frac_comum']:.4f}")
    print(f"  reservados p/ teste: {lines['reservados_teste']}; sorteáveis no treino: "
          f"{lines['reservados_sorteaveis_no_treino']}; sorteados no treino: "
          f"{lines['reservados_sorteados_no_treino']}")
    print(f"  vazão: {gen['imagens_por_segundo']:.1f} img/s; "
          f"{gen['bytes_por_imagem'] / 1024:.1f} KiB/img; rejeições: {gen['rejeicoes_contraste']}")
    if bre:
        print(f"  BRESSAY: {bre['linhas_mantidas']} linhas; altura média {bre['altura_media']:.0f}px "
              f"(sintético {gen['altura_media']:.0f}px)")
