# Resultados

Cada número do relatório final (`POC/salmoria-gabriel/relatorio.tex`) sai de um arquivo desta pasta. Os `.md` são os relatórios legíveis, os `.json` têm os mesmos números com mais casas e os `.jsonl` são as predições brutas de cada modelo, uma linha por página ou por linha manuscrita.

Nomes dos modelos nas pastas: `base` e `base_g4` são o Chandra OCR 2 original (o `base_g4` é a execução da segunda etapa, na RTX PRO 6000), `ft` é o lora_v0 (linhas), e `lora_v1`, `lora_v2`, `lora_v2_fp8` e `lora_v2_int4` são os adaptadores de páginas. Nos testes de páginas, `teste_local` é o teste difícil e `forms_v2_normal` o teste normal.

| No relatório | Arquivo | Gerado por |
|---|---|---|
| Experimento 1, vocabulário, amostragem e partições | `exp1/resultados.json`, `exp1/tabela_*.tex` | `python -m ocr06 exp1` |
| Experimento 1, testes da avaliação de linhas e do `guard.py` | `exp2_integracao/resultados.json` | `python -m ocr06 exp2` |
| Experimento 1, testes do avaliador de páginas | `../tests/` | `pytest` |
| Experimento 2 e Apêndice B (linhas) | `modelos/comparacao.md`; nomes inéditos e revisão do `guard.py` em `modelos/<modelo>/<prompt>/<teste>.metricas.json` | `scripts/run.sh avaliacao` |
| Experimento 3 (mesmas 38 certidões) | `paginas/mesmas_38_paginas.md`, a partir de `paginas/avaliacao_metade_local_aval.json` e `paginas/avaliacao_teste_local.json`; OCRSD em `paginas/avaliacao_metade_ocrsd.md` | `scripts/mesmas_38_paginas.py` |
| Experimento 4, testes difícil e normal, por classe e por documento | `paginas/avaliacao_teste_local.md`, `paginas/avaliacao_forms_v2_normal.md` | `python -m ocr06.pages_eval` |
| Experimento 4, lora_v2 contra lora_v1 | `paginas/avaliacao_*_v2_vs_v1.md` | `python -m ocr06.pages_eval --ref lora_v1` |
| Experimento 4, figuras por classe e certidão de demonstração | figuras em `apresentacoes/2026-11-23_workshop/figs/`, copiadas para `POC/salmoria-gabriel/figuras/` | `scripts/figs_workshop.py` |
| Experimento 4, leituras de cada campo (exemplos de nomes) | `paginas/erros_teste_local.md`, `paginas/erros_forms_v2_normal.md` | `scripts/erros_paginas.py` |
| Experimento 4, tipos de erro que sobram nos nomes e distância dos campos corrigidos | `paginas/erros_restantes.md` | `scripts/erros_restantes.py` |
| Experimento 4, nomes vistos e inéditos | `paginas/memorizacao_nomes.md` | `scripts/memorizacao_paginas.py` |
| Experimento 4, texto impresso | seção "Página" de `paginas/avaliacao_teste_local.md` | `python -m ocr06.pages_eval` |
| Experimento 5 (OCRSD) | `paginas/avaliacao_teste_ocrsd_94.md` (por classe e "Por writing") | `python -m ocr06.pages_eval --set teste_ocrsd_94` |
| Experimento 6 (quantização e tempo) | `paginas/avaliacao_*_quant_vs_v2.md`, `paginas/*/teste_local.tempo.json`, `paginas/lote1_*/` | `python -m ocr06.pages_eval --ref lora_v2` |
| Experimento 7 (BRESSAY e XFUND-PT) | `paginas/comparacao_real.md`, `paginas/avaliacao_xfund_hw.md` | `python -m ocr06.pages_real score` (BRESSAY), `python -m ocr06.pages score` (XFUND-PT) |
| Seção 8, consistência entre campos | `paginas/consistencia_campos.md` | `scripts/consistencia_campos.py` |

`hw_bakeoff/` é a comparação dos geradores neurais de escrita (Graves, VATr++ e Emuru) feita antes de escolher os dois que entraram no gerador de certidões. Os arquivos `paginas/*_s4.*` e `paginas/antes_s4/` são avaliações intermediárias com menos modelos (só o Chandra, ou Chandra, lora_v1 e lora_v2), substituídas pelas que não têm sufixo, e não entram no relatório.
