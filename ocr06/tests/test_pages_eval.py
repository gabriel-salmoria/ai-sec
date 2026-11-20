"""Testes do placar de páginas (ocr06.pages_eval) com gabarito e predições sintéticos.

    .venv-cputest/bin/python -m pytest tests/test_pages_eval.py -q
"""
from pathlib import Path

import pytest

from ocr06 import pages_eval as pe

# Formulário fictício de cima para baixo: (rótulo impresso, campo, classe, valor, caixa 0-1000)
FORM = [
    ("NOME", "nome", "name", "Henrique Almeida Batista", (100, 100, 600, 130)),
    ("CIDADE", "cidade", "place", "Florianópolis/SC", (100, 200, 600, 230)),
    ("ANO", "ano", "number", "1980", (700, 200, 800, 230)),
    ("DIA", "dia", "number", "17", (820, 200, 900, 230)),
    ("MÃE", "mae", "name", "Maria das Dores Conceição", (100, 300, 600, 330)),
    ("PAI", "pai", "name", "José Ribamar Pereira", (100, 400, 600, 430)),
    ("REGIME", "regime", "closed", "COMUNHÃO PARCIAL DE BENS", (100, 500, 600, 530)),
    ("TESTEMUNHA", "testemunha", "name", "Antônia Ferreira Lima", (100, 600, 600, 630)),
    ("MATRÍCULA", "matricula", "number", "406524.01.55.1980", (100, 700, 600, 730)),
]


def gold_row(pid="p1", form=FORM, stripped=(), **meta):
    fields = [{"label": lab, "text": val, "cls": cls, "accent_stripped": lab in stripped,
               "bbox_1000": list(box)} for _, lab, cls, val, box in form]
    return {"id": pid, "image": "", "size": [1000, 1000], "template": "t", "split": "test",
            "fields": fields, **meta}


def block(box, text, label="Text"):
    return f'<div data-bbox="{box[0]} {box[1]} {box[2]} {box[3]}" data-label="{label}"><p>{text}</p></div>'


def render(form=FORM, values=None, upto=None, footer=True, printed=None):
    """Saída no formato do Chandra: rótulo impresso (logo acima) e valor em blocos."""
    values = values or {}
    printed = printed or {}
    out = [block((300, 20, 700, 50), "CERTIDÃO DE TESTE", "Section-Header")]
    for i, (lab_txt, lab, _, val, box) in enumerate(form):
        if upto is not None and i >= upto:
            break
        out.append(block((box[0], box[1] - 25, box[2], box[1] - 5), printed.get(lab, lab_txt)))
        out.append(block(box, values.get(lab, val)))
    if footer and upto is None:
        out.append(block((100, 900, 600, 930), "Assinatura do Oficial"))
    return "\n".join(out)


def pred(text, fim="stop", pid="p1"):
    return {"id": pid, "pred": text, "tokens": len(text) // 3, "fim": fim}


def fields(row):
    return pe.fields_of(row, row["size"])


def run(preds_by_model, gold=None, **kw):
    gold = gold or [gold_row()]
    return pe.evaluate(gold, {m: {p["id"]: p for p in ps} for m, ps in preds_by_model.items()},
                       Path("."), **kw)


def test_perfect_prediction_is_100():
    page = pe.score_page(fields(gold_row()), pred(render()))
    main = [r for r in page["campos"] if not r["short"]]
    assert main and all(r["exato_livre"] and r["exato_local"] for r in main)
    assert page["completude"] == 1.0
    assert not page["truncada_fim"] and not page["truncada_cauda"] and not page["laco_repeticao"]
    res = run({"base": [pred(render())]})
    s = res["resumo"]["base"]
    assert s["todos"]["exato_livre"] == 1.0 and s["todos"]["exato_local"] == 1.0
    assert s["nomes"]["exato_local"] == 1.0 and s["nomes"]["campos"] == 4
    assert s["todos"]["cer_livre"] == 0.0


def test_truncated_by_length_is_flagged():
    page = pe.score_page(fields(gold_row()), pred(render(), fim="length"))
    assert page["truncada_fim"]


def test_truncated_tail_is_flagged():
    # para no 6º campo (sem rodapé): os últimos campos faltam e nada chega à altura deles
    page = pe.score_page(fields(gold_row()), pred(render(upto=6)))
    assert page["truncada_cauda"] and not page["truncada_fim"]
    res = run({"base": [pred(render(upto=6))]})
    assert res["resumo"]["base"]["truncadas"] == 1.0


def test_skipped_fields_with_footer_are_not_truncation():
    # os mesmos campos faltando, mas a saída chega ao rodapé: é campo pulado, não corte
    vals = {"testemunha": "", "matricula": "", "regime": ""}
    page = pe.score_page(fields(gold_row()), pred(render(values=vals)))
    assert not page["truncada_cauda"]
    assert page["completude"] < 1.0


def test_looped_prediction_is_flagged():
    loop = render(upto=3) + "\n" + "\n".join([block((100, 300, 600, 330), "Nome: Nascimento da Silva")] * 12)
    page = pe.score_page(fields(gold_row()), pred(loop))
    assert page["laco_repeticao"]
    assert page["repeticao"]["repeticoes"] >= 10


def test_punctuation_leaders_are_not_loops_unless_very_long():
    leaders = render() + block((100, 950, 900, 970), ". " * 40)
    assert not pe.score_page(fields(gold_row()), pred(leaders))["laco_repeticao"]
    dashes = render() + block((100, 950, 900, 970), "- " * 400)
    assert pe.score_page(fields(gold_row()), pred(dashes))["laco_repeticao"]


def test_much_longer_output_than_other_model_counts_as_loop():
    long_txt = render() + "\n" + "\n".join(block((100, 950, 900, 970), f"linha extra {i} " + "x" * i)
                                          for i in range(60))
    res = run({"base": [pred(render())], "ft": [pred(long_txt)]})
    assert res["por_pagina"]["ft"][0]["longa"] and res["resumo"]["ft"]["lacos"] == 1.0
    assert not res["por_pagina"]["base"][0]["longa"]


def test_digit_split_number_still_counts():
    vals = {"ano": "1 9 8 0", "matricula": "406524 01 55 1980"}
    page = pe.score_page(fields(gold_row()), pred(render(values=vals)))
    by = {r["label"]: r for r in page["campos"]}
    assert by["ano"]["exato_livre"] and by["ano"]["exato_local"]
    assert by["matricula"]["exato_livre"] and by["matricula"]["exato_local"]
    # nomes não são compactados: espaço a mais é erro
    page = pe.score_page(fields(gold_row()), pred(render(values={"nome": "Henrique AlmeidaBatista"})))
    assert not {r["label"]: r for r in page["campos"]}["nome"]["exato_livre"]


def test_accent_stripped_fields_are_ignored():
    row = gold_row(stripped=("regime", "mae"))
    vals = {"regime": "COMUNHAO PARCIAL DE BENS", "mae": "Maria das Dores Conceicao"}
    page = pe.score_page(fields(row), pred(render(values=vals)))
    labels = {r["label"] for r in page["campos"]}
    assert "regime" not in labels and "mae" not in labels
    res = run({"base": [pred(render(values=vals))]}, gold=[row])
    assert res["resumo"]["base"]["todos"]["exato_livre"] == 1.0
    assert res["campos_sem_acento_ignorados"] == 2


def test_short_fields_are_reported_apart():
    page = pe.score_page(fields(gold_row()), pred(render()))
    short = [r["label"] for r in page["campos"] if r["short"]]
    assert short == ["dia"]
    res = run({"base": [pred(render(values={"dia": "71"}))]})
    s = res["resumo"]["base"]
    assert s["todos"]["exato_livre"] == 1.0          # o curto errado não entra no total
    assert s["curtos"]["campos"] == 1


def test_localised_match_rejects_value_in_wrong_place():
    # nome lido errado no lugar dele, mas escrito certo em outro bloco (como na filiação)
    txt = render(values={"testemunha": "Antônio Ferreira Lima"}) + "\n" + \
        block((100, 800, 600, 830), "filha de Antônia Ferreira Lima")
    by = {r["label"]: r for r in pe.score_page(fields(gold_row()), pred(txt))["campos"]}
    assert by["testemunha"]["exato_livre"] and not by["testemunha"]["exato_local"]


def test_missing_gold_ids_are_skipped():
    res = run({"base": [pred(render()), pred(render(), pid="sem_gabarito")]})
    assert res["paginas"] == 1 and res["predicoes_sem_gabarito"]["base"] == 1


def test_printed_change_ignores_handwriting_but_sees_labels():
    row = gold_row()
    base = pred(render())
    other_hw = pred(render(values={"nome": "Henrique Almeida Bautista", "cidade": "Florianopolis/SC"}))
    other_print = pred(render(printed={"nome": "N0ME", "regime": "REGIME DE BENS"}))
    res = run({"base": [base], "a": [other_hw], "b": [other_print]}, gold=[row])
    assert res["resumo"]["a"]["impresso_cer"] == 0.0
    assert res["resumo"]["b"]["impresso_cer"] > 0.0
    up = pred(render(printed={"nome": "Nome"}))
    res = run({"base": [base], "c": [up]}, gold=[row])
    assert res["resumo"]["c"]["impresso_cer"] > 0 and res["resumo"]["c"]["impresso_cer_sem_caixa"] == 0


def test_paired_comparison_and_mcnemar():
    gold = [gold_row(pid=f"p{i}") for i in range(10)]
    base = [pred(render(values={"nome": "Henrique Almeida Batisla"}), pid=f"p{i}") for i in range(10)]
    ft = [pred(render(), pid=f"p{i}") for i in range(10)]
    res = run({"base": base, "ft": ft}, gold=gold, n_boot=500, seed=1)
    v = res["pareado"]["ft"]["campos/exato_livre"]
    assert v["so_ref"] == 0 and v["so_cand"] == 10
    assert v["delta"] == pytest.approx(10 / 80)
    assert v["ic95"][0] <= v["delta"] <= v["ic95"][1]
    assert v["mcnemar_p"] == pytest.approx(2 / 2 ** 10)
    n = res["pareado"]["ft"]["nomes/exato_livre"]
    assert n["delta"] == pytest.approx(10 / 40)
    again = run({"base": base, "ft": ft}, gold=gold, n_boot=500, seed=1)
    assert again["pareado"]["ft"]["campos/exato_livre"]["ic95"] == v["ic95"]
    assert pe.mcnemar(0, 0) == 1.0 and pe.mcnemar(5, 5) == 1.0


def test_breakdowns_present_only_for_keys_in_gold():
    gold = [gold_row(pid="a", level=1, writing="font"), gold_row(pid="b", level=3, writing="neural")]
    res = run({"base": [pred(render(), pid="a"), pred(render(upto=5), pid="b")]}, gold=gold)
    assert set(res["recortes"]) == {"template", "level", "writing", "split"}
    assert res["recortes"]["level"]["1"]["base"]["completude"] == 1.0
    assert res["recortes"]["level"]["3"]["base"]["truncadas"] == 1.0
    assert "avaliação" in pe.report(res, "teste").lower()


def test_infix_span_and_blocks():
    d, s, e = pe.infix_span("Batista", "Henrique Almeida Batista e outros")
    assert (d, "Henrique Almeida Batista e outros"[s:e]) == (0, "Batista")
    d, s, e = pe.infix_span("Batista", "Henrique Almeida Bastista")
    assert d == 1 and "Henrique Almeida Bastista"[s:e] in ("Bastista", "astista", "Bstista")
    bl = pe.parse_blocks(render(upto=1) + '<div data-bbox="1 2 3 4" data-label="Text"><p>cortad')
    assert bl[-1].bbox == (1, 2, 3, 4) and bl[-1].text == "cortad"
