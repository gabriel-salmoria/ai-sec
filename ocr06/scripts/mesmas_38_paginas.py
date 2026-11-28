"""Os adaptadores das duas etapas nas mesmas 38 certidões do teste difícil (Experimento 3 do
relatório final).

    python3 scripts/mesmas_38_paginas.py

O Chandra e o lora_v0 vêm de avaliacao_metade_local_aval.json (execução da primeira etapa); o
lora_v1, o lora_v2 e o Chandra da segunda execução (base_g4) vêm dos campos dessas mesmas páginas
em avaliacao_teste_local.json. Grava experiments/paginas/mesmas_38_paginas.md."""
import json
from pathlib import Path

P = Path(__file__).resolve().parents[1] / "experiments" / "paginas"
antiga = json.load(open(P / "avaliacao_metade_local_aval.json", encoding="utf-8"))
nova = json.load(open(P / "avaliacao_teste_local.json", encoding="utf-8"))
ids = {p["id"] for p in antiga["por_pagina"]["base"]}

L = ["# Mesmas 38 certidões do teste difícil", "",
     "Acerto exato local (%), sem os campos curtos. base: Chandra na execução da primeira etapa; "
     "base_g4: Chandra na execução da segunda etapa.", "",
     "| Execução | Modelo | Campos | Exatos | Nomes | Nomes exatos |", "|---|---|---|---|---|---|"]
for execucao, res, modelos in (("primeira etapa", antiga, ("base", "lora_v0")),
                               ("segunda etapa", nova, ("base_g4", "lora_v1", "lora_v2"))):
    for m in modelos:
        f = [x for x in res["por_campo"][m] if x["id"] in ids and not x["short"]]
        n = [x for x in f if x["cls"] == "name"]
        L.append(f"| {execucao} | {m} | {len(f)} | {100 * sum(x['exato_local'] for x in f) / len(f):.1f} | "
                 f"{len(n)} | {100 * sum(x['exato_local'] for x in n) / len(n):.1f} |")
(P / "mesmas_38_paginas.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print("\n".join(L))
