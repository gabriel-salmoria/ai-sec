"""Figuras da apresentação do workshop (apresentacoes/2026-11-23_workshop/figs): recortes ampliados, a mesma
certidão com os campos certos e errados de cada modelo e os gráficos de resultados.

    .venv/bin/python scripts/figs_workshop.py
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ocr06.pages_eval import MARGIN, compact, fields_of, infix_span, overlaps, page_size, parse_blocks  # noqa: E402

OUT = ROOT.parent / "apresentacoes" / "2026-11-23_workshop" / "figs"
P = ROOT / "experiments" / "paginas"
DATA = ROOT / "data"
CHANDRA, V1, V2 = "#5b84c4", "#d0893b", "#12907d"  # validate_palette.js
INK, INK2 = "#0b0b0b", "#52514e"
CERTO, ERRADO = (27, 138, 98), (192, 57, 43)

FONTES = Path("/usr/share/texmf-dist/fonts/opentype/adobe/sourcesanspro")
for nome in ("SourceSansPro-Regular.otf", "SourceSansPro-Semibold.otf"):
    font_manager.fontManager.addfont(str(FONTES / nome))
plt.rcParams.update({"font.family": "Source Sans Pro", "pdf.fonttype": 3})


def br(v: float, casas: int = 0) -> str:
    return f"{v:.{casas}f}".replace(".", ",")


def rows(name: str) -> dict:
    return {r["id"]: r for r in map(json.loads, open(name, encoding="utf-8"))}


def recortes() -> None:
    """Campos ampliados 4x (Lanczos) para ocupar a largura do slide."""
    exemplos = {"claudemar": ("teste_local", "forms_v1_00925", [149, 1130, 569, 1181]),
                "jenifer": ("teste_local", "forms_v1_00733", [134, 421, 443, 464]),
                "ribeira": ("teste_local", "forms_v1_00042", [138, 1539, 391, 1568]),
                "sus": ("teste_local", "forms_v1_00437", [973, 602, 1450, 631])}
    gold = rows(DATA / "pages" / "teste_local" / "pages.jsonl")
    for chave, pid, nome in (("maikon", "forms_v1_00153", "Maikon Giordano Cirino"),
                             ("guiomar", "forms_v1_00572", "Guiomar Schiavon Arrabal"),
                             ("alcineia", "forms_v1_00925", "Alcineia Scalabrin Nakajima")):
        box = next(f["box"] for f in gold[pid]["fields"] if f.get("text") == nome)
        exemplos[chave] = ("teste_local", pid, box)
    for nome, (_, pid, (x0, y0, x1, y1)) in exemplos.items():
        im = Image.open(DATA / gold[pid]["image"]).convert("RGB")
        py = {"sus": 3, "guiomar": 4, "alcineia": 4}.get(nome, 10)  # sem o rótulo do campo vizinho
        topo = y0 + 6 if nome == "alcineia" else max(0, y0 - py)  # corta o rótulo impresso logo acima
        c = im.crop((max(0, x0 - 12), topo, x1 + 12, y1 + py))
        c.resize((c.width * 4, c.height * 4), Image.LANCZOS).save(OUT / f"ex_{nome}.jpg", quality=93)


def certidao() -> None:
    """A mesma página com um quadro verde (certo) ou vermelho (errado) em cada campo avaliado."""
    pid = "forms_v1_00925"
    g = rows(DATA / "pages" / "teste_local" / "pages.jsonl")[pid]
    base = Image.open(DATA / g["image"]).convert("RGB")
    W, H = base.size
    topo, corte = 512, (100, 512, 1460, 1600)  # da matrícula para baixo
    base.crop((110, 515, 1385, 1232)).save(OUT / "gerador_cheia.jpg", quality=93)  # 16:9, ocupa o slide todo
    campos = [f for f in fields_of(g, page_size(g, DATA)) if not f.stripped and not f.short and f.box is not None
              and f.box[1] * H / 1000 >= topo]
    for modelo, saida in (("base_g4", "original"), ("lora_v2", "ajustado")):
        blocos = parse_blocks(rows(P / modelo / "teste_local.jsonl")[pid]["pred"])
        camada = Image.new("RGBA", base.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(camada)
        certos = 0
        for f in campos:
            hay = " ".join(b.text for b in blocos if overlaps(b.bbox, f.box, MARGIN))
            ok = infix_span(f.cmp, compact(hay) if f.cls == "number" else hay)[0] == 0
            certos += ok
            cor = CERTO if ok else ERRADO
            x0, y0, x1, y1 = (f.box[0] * W / 1000 - 5, f.box[1] * H / 1000 - 5,
                              f.box[2] * W / 1000 + 5, f.box[3] * H / 1000 + 5)
            d.rectangle((x0, y0, x1, y1), fill=cor + ((46 if ok else 74),), outline=cor + (255,), width=5)
            # marca além da cor: visto para certo, X para errado
            bx, by, r = x1 - 2, y0 + 2, 15
            d.ellipse((bx - r, by - r, bx + r, by + r), fill=cor + (255,))
            if ok:
                d.line((bx - 8, by, bx - 2, by + 7, bx + 9, by - 7), fill="white", width=4)
            else:
                d.line((bx - 7, by - 7, bx + 7, by + 7), fill="white", width=4)
                d.line((bx - 7, by + 7, bx + 7, by - 7), fill="white", width=4)
        im = Image.alpha_composite(base.convert("RGBA"), camada).convert("RGB")
        im.crop(corte).save(OUT / f"certidao_{saida}.jpg", quality=92)
        print(f"certidão {saida}: {certos}/{len(campos)}")


def limpa(ax) -> None:
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color(INK2)
    ax.set_yticks([])
    ax.tick_params(axis="x", length=0, pad=2)


CLASSES = [("todos", "Todos"), ("name", "Nomes"), ("date", "Datas"), ("number", "Números"),
           ("closed", "Opções fixas"), ("place", "Lugares"), ("text", "Texto livre")]


def grafico_classes(conjunto: str, saida: str) -> None:
    """Acerto exato por classe de campo, com os três modelos em BF16."""
    res = json.load(open(P / f"avaliacao_{conjunto}.json"))["resumo"]
    modelos = (("base_g4", "Chandra OCR 2", CHANDRA), ("lora_v1", "lora_v1", V1), ("lora_v2", "lora_v2", V2))
    fig, ax = plt.subplots(figsize=(5.67, 2.42))
    w = 0.27
    for k, (m, rotulo, cor) in enumerate(modelos):
        for g, (c, _) in enumerate(CLASSES):
            bloco = res[m]["todos"] if c == "todos" else res[m]["por_classe"][c]
            v = 100 * bloco["exato_local"]
            x = g + (k - 1) * (w + 0.012)
            ax.bar(x, v, w, color=cor, label=rotulo if g == 0 else None)
            ax.text(x, v + 1.4, str(int(v + 0.5 + 1e-9)), ha="center", va="bottom", fontsize=9.6, color=INK,
                    fontweight="semibold" if m == "lora_v2" else "normal")
    n = {c: (res["lora_v2"]["todos"] if c == "todos" else res["lora_v2"]["por_classe"][c])["campos"] for c, _ in CLASSES}
    ax.set_xticks(range(len(CLASSES)), [f"{t}\n{n[c]:,}".replace(",", ".") for c, t in CLASSES], fontsize=10.2, color=INK)
    ax.axvline(0.5, color="#d8d7d2", lw=0.8)
    ax.set_ylim(0, 108)
    ax.set_xlim(-0.55, len(CLASSES) - 0.45)
    limpa(ax)
    fig.legend(loc="upper right", ncol=3, frameon=False, fontsize=10.2, bbox_to_anchor=(1.0, 1.04),
               handlelength=1.1, columnspacing=1.2)
    fig.tight_layout(rect=(0, 0, 1, 0.93), pad=0.1)
    fig.savefig(OUT / saida)
    plt.close(fig)


def grafico_fora() -> None:
    real = json.load(open(P / "comparacao_real.json"))["bressay"]
    xf = json.load(open(P / "avaliacao_xfund_hw.json"))["resumo"]
    paineis = [("BRESSAY: CER da página (menor é melhor)", 100 * real["base"]["cer"], 100 * real["lora_v2"]["cer"]),
               ("XFUND-PT: campos exatos (maior é melhor)",
                100 * xf["base"]["todos"]["exato_livre"], 100 * xf["lora_v2"]["todos"]["exato_livre"])]
    fig, axes = plt.subplots(1, 2, figsize=(3.75, 2.3))
    for ax, (titulo, a, b) in zip(axes, paineis):
        for i, (x, cor) in enumerate(((a, CHANDRA), (b, V2))):
            ax.bar(i, x, 0.66, color=cor)
            ax.text(i, x + 1.2, f"{br(x, 1)}%", ha="center", va="bottom", fontsize=11, color=INK)
        ax.set_xticks(range(2), ["Chandra", "lora_v2"], fontsize=9.5, color=INK)
        ax.set_ylim(0, 64)
        ax.set_title(titulo.replace(": ", "\n"), fontsize=9, color=INK)
        limpa(ax)
    fig.tight_layout(pad=0.2, w_pad=1.2)
    fig.savefig(OUT / "g_fora.pdf")
    plt.close(fig)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    recortes()
    certidao()
    grafico_classes("teste_local", "g_dificil.pdf")
    grafico_classes("forms_v2_normal", "g_normal.pdf")
    grafico_fora()
