"""Quanto dos erros em nomes seria marcado para revisão por uma checagem de consistência com
outros campos da mesma página, e quantos nomes certos seriam marcados à toa.

    .venv/bin/python scripts/consistencia_campos.py

Duas regras, aplicadas à leitura de cada modelo:
- sexo: o prenome lido (primeira palavra) tem, no léxico do IBGE, o gênero oposto ao sexo lido
  na região do campo sexo (nascimento e óbito);
- filiação: alguma palavra do nome lido, fora a primeira, não aparece no texto lido na região
  dos campos dos genitores da mesma pessoa (nascimento, óbito e casamento CNJ).
A leitura do nome é a mesma da avaliação (o trecho da região do campo mais parecido com o
valor certo); a do sexo e a dos genitores é o texto inteiro da região, sem usar o gabarito.
Grava experiments/paginas/consistencia_campos.md."""
import csv
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ocr06.pages_eval import MARGIN, fields_of, infix_span, overlaps, page_size, parse_blocks  # noqa: E402

DATA, OUT = ROOT / "data", ROOT / "experiments" / "paginas"
MODELOS = ("base_g4", "lora_v2")
SEXO = {"certidao_nascimento_cnj": "nome", "certidao_obito": "nome"}
FILIACAO = {
    "certidao_nascimento_cnj": {"nome": ["genitor1_nome", "genitor2_nome"],
                                "genitor1_nome": ["avos1"], "genitor2_nome": ["avos2"]},
    "certidao_obito": {"nome": ["genitores"]},
    "certidao_casamento_cnj": {"conjuge1_nome_habilitacao": ["conjuge1_genitores"],
                               "conjuge2_nome_habilitacao": ["conjuge2_genitores"]},
}


def chave(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).upper()


genero = {}
with open(DATA / "lexicon" / "prenomes.csv", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if r["gender"] in ("M", "F"):
            genero[r["key"]] = r["gender"]


def regiao(box, blocos) -> str:
    return " ".join(b.text for b in blocos if overlaps(b.bbox, box, MARGIN))


def campos_por_id(row, size):
    """field_id -> (Field, campo bruto), na mesma ordem de fields_of."""
    brutos = [f for f in row["fields"] if f.get("kind", "manuscrito") == "manuscrito"]
    return {b["field_id"]: (f, b) for f, b in zip(fields_of(row, size), brutos)}


def avaliar(conjunto: str) -> dict:
    gold = [json.loads(l) for l in open(DATA / "pages" / conjunto / "pages.jsonl", encoding="utf-8")]
    preds = {m: {r["id"]: r for r in map(json.loads, open(OUT / m / f"{conjunto}.jsonl", encoding="utf-8"))}
             for m in MODELOS}
    res = {regra: {m: {"campos": 0, "errados": 0, "errados_marcados": 0, "certos_marcados": 0}
                   for m in MODELOS + ("gabarito",)} for regra in ("sexo", "filiacao")}
    for row in gold:
        t = row["template"]
        if t not in SEXO and t not in FILIACAO:
            continue
        cid = campos_por_id(row, page_size(row, DATA))
        for m in MODELOS + ("gabarito",):
            if m == "gabarito":
                leitura = lambda f: f.text  # noqa: E731
                texto_regiao = lambda fid: cid[fid][0].text if fid in cid else ""  # noqa: E731
            else:
                blocos = parse_blocks(preds[m][row["id"]]["pred"] or "")

                def leitura(f, blocos=blocos):
                    hay = regiao(f.box, blocos)
                    d, s, e = infix_span(f.cmp, hay)
                    return hay[s:e]

                def texto_regiao(fid, blocos=blocos):
                    return regiao(cid[fid][0].box, blocos) if fid in cid else ""

            casos = []
            if t in SEXO and SEXO[t] in cid and "sexo" in cid:
                f = cid[SEXO[t]][0]
                lido = leitura(f).split()
                sx = chave(texto_regiao("sexo"))
                s = "M" if "MASC" in sx else "F" if "FEM" in sx else None
                g = genero.get(chave(lido[0])) if lido else None
                casos.append(("sexo", f, lido, bool(s and g and s != g)))
            for pessoa, pais in FILIACAO.get(t, {}).items():
                if pessoa not in cid or not all(p in cid for p in pais):
                    continue
                f = cid[pessoa][0]
                lido = leitura(f).split()
                palavras_pais = set(re.findall(r"\w+", chave(" ".join(texto_regiao(p) for p in pais))))
                sobrenomes = re.findall(r"\w+", chave(" ".join(lido[1:])))
                casos.append(("filiacao", f, lido, any(w not in palavras_pais for w in sobrenomes)))
            for regra, f, lido, marcado in casos:
                if f.stripped:
                    continue
                r = res[regra][m]
                certo = " ".join(lido) == " ".join(f.cmp.split())
                r["campos"] += 1
                r["errados"] += not certo
                r["errados_marcados"] += marcado and not certo
                r["certos_marcados"] += marcado and certo
    return res


L = ["# Consistência entre campos como sinal de revisão", "",
     "Campos de nome aos quais cada regra se aplica, erros de leitura e quantos seriam marcados. "
     "A linha gabarito aplica a regra aos valores certos: o que ela marca são alarmes que nem um "
     "leitor perfeito evitaria.", ""]
for conjunto in ("teste_local", "forms_v2_normal"):
    res = avaliar(conjunto)
    L += [f"## {conjunto}", "", "| Regra | Leitura | Campos | Errados | Errados marcados | Certos marcados |",
          "|---|---|---|---|---|---|"]
    for regra, por_modelo in res.items():
        for m, r in por_modelo.items():
            L.append(f"| {regra} | {m} | {r['campos']} | {r['errados']} | {r['errados_marcados']} | {r['certos_marcados']} |")
    L.append("")
(OUT / "consistencia_campos.md").write_text("\n".join(L), encoding="utf-8")
print("\n".join(L))
