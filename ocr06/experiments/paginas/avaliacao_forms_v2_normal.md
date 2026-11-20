# Avaliação de páginas inteiras: forms_v2_normal

100 páginas com gabarito e predição de todos os modelos. 0 campos cuja tinta perdeu os acentos ficam de fora. Campos de até 3 caracteres vão para uma tabela à parte. Valores em %.

Livre: o valor pode estar em qualquer ponto da saída. Local: só nos blocos cuja caixa encosta na do campo. CER = distância de edição / tamanho do campo. Campos numéricos comparados só por letras e dígitos.

## Campos manuscritos

| Modelo | Campos | Exatos livre | CER livre | Exatos local | CER local | Nomes | Nomes exatos livre | Nomes exatos local | Nomes CER local |
|---|---|---|---|---|---|---|---|---|---|
| base_g4 | 2668 | 56.4 | 9.6 | 55.8 | 10.4 | 488 | 40.4 | 40.4 | 9.0 |
| lora_v1 | 2668 | 69.2 | 5.4 | 69.2 | 5.4 | 488 | 44.5 | 44.5 | 7.5 |
| lora_v2 | 2668 | 72.0 | 5.0 | 72.0 | 5.0 | 488 | 50.2 | 50.2 | 7.1 |
| lora_v2_fp8 | 2668 | 71.9 | 5.1 | 71.9 | 5.1 | 488 | 49.6 | 49.6 | 7.1 |
| lora_v2_int4 | 2668 | 71.6 | 5.2 | 71.6 | 5.2 | 488 | 49.4 | 49.4 | 7.3 |

### Por classe de campo

| Classe | Modelo | Campos | Exatos livre | CER livre | Exatos local | CER local |
|---|---|---|---|---|---|---|
| closed | base_g4 | 519 | 67.4 | 8.3 | 67.1 | 10.3 |
| closed | lora_v1 | 519 | 84.0 | 1.9 | 84.0 | 2.1 |
| closed | lora_v2 | 519 | 85.0 | 1.5 | 85.0 | 1.7 |
| closed | lora_v2_fp8 | 519 | 85.0 | 1.5 | 85.0 | 1.7 |
| closed | lora_v2_int4 | 519 | 85.0 | 1.7 | 85.0 | 1.8 |
| date | base_g4 | 170 | 81.8 | 1.6 | 81.2 | 2.2 |
| date | lora_v1 | 170 | 94.7 | 0.4 | 94.7 | 0.4 |
| date | lora_v2 | 170 | 96.5 | 0.3 | 96.5 | 0.3 |
| date | lora_v2_fp8 | 170 | 95.9 | 0.4 | 95.9 | 0.4 |
| date | lora_v2_int4 | 170 | 95.3 | 0.3 | 95.3 | 0.3 |
| name | base_g4 | 488 | 40.4 | 8.8 | 40.4 | 9.0 |
| name | lora_v1 | 488 | 44.5 | 7.5 | 44.5 | 7.5 |
| name | lora_v2 | 488 | 50.2 | 7.1 | 50.2 | 7.1 |
| name | lora_v2_fp8 | 488 | 49.6 | 7.1 | 49.6 | 7.1 |
| name | lora_v2_int4 | 488 | 49.4 | 7.3 | 49.4 | 7.3 |
| number | base_g4 | 795 | 58.9 | 11.0 | 58.2 | 11.8 |
| number | lora_v1 | 795 | 77.0 | 4.8 | 76.9 | 4.9 |
| number | lora_v2 | 795 | 80.8 | 3.8 | 80.8 | 3.8 |
| number | lora_v2_fp8 | 795 | 79.4 | 4.1 | 79.4 | 4.2 |
| number | lora_v2_int4 | 795 | 79.2 | 4.3 | 79.2 | 4.3 |
| place | base_g4 | 279 | 66.7 | 8.5 | 65.2 | 10.0 |
| place | lora_v1 | 279 | 72.8 | 7.0 | 72.8 | 7.2 |
| place | lora_v2 | 279 | 70.3 | 8.1 | 70.3 | 8.2 |
| place | lora_v2_fp8 | 279 | 73.1 | 7.9 | 73.1 | 8.0 |
| place | lora_v2_int4 | 279 | 71.0 | 8.1 | 71.0 | 8.5 |
| text | base_g4 | 417 | 39.3 | 12.0 | 38.8 | 12.4 |
| text | lora_v1 | 417 | 52.0 | 6.6 | 52.0 | 6.6 |
| text | lora_v2 | 417 | 56.1 | 6.2 | 56.1 | 6.2 |
| text | lora_v2_fp8 | 417 | 56.8 | 6.3 | 56.8 | 6.3 |
| text | lora_v2_int4 | 417 | 56.8 | 6.2 | 56.8 | 6.2 |

### Campos curtos (até 3 caracteres, fora dos totais)

| Modelo | Campos | Exatos livre | Exatos local |
|---|---|---|---|
| base_g4 | 1048 | 92.7 | 88.6 |
| lora_v1 | 1048 | 95.0 | 93.7 |
| lora_v2 | 1048 | 96.0 | 95.2 |
| lora_v2_fp8 | 1048 | 95.7 | 94.8 |
| lora_v2_int4 | 1048 | 95.6 | 94.9 |

## Página

Completude: fração dos campos achados com CER <= 0.2 (livre). Truncada: `fim = length` ou últimos campos ausentes sem bloco na altura deles. Laço: trecho repetido em sequência (>= 100 caracteres, >= 3 vezes) ou saída >= 1.5x a dos outros modelos. Impresso: CER entre a saída do modelo e a da referência (base_g4) depois de apagar os valores manuscritos.

| Modelo | Páginas | Completude | Truncadas | Laços | Impresso CER vs ref | Idem, sem maiúsc./minúsc. | Páginas com impresso alterado |
|---|---|---|---|---|---|---|---|
| base_g4 | 100 | 85.0 | 6.0 | 3.0 | - | - | - |
| lora_v1 | 100 | 92.8 | 0.0 | 0.0 | 31.93 | 31.67 | 95.0 |
| lora_v2 | 100 | 93.1 | 0.0 | 0.0 | 32.03 | 31.78 | 96.0 |
| lora_v2_fp8 | 100 | 92.8 | 0.0 | 0.0 | 31.96 | 31.69 | 96.0 |
| lora_v2_int4 | 100 | 92.5 | 0.0 | 0.0 | 31.91 | 31.65 | 98.0 |

## Comparação pareada com base_g4

Diferença em pontos percentuais (modelo - referência) nas mesmas páginas e campos; IC de 95% por bootstrap pareado sobre páginas; McNemar exato campo a campo (só ref = acertos só da referência, só modelo = acertos só do modelo).

| Modelo | Métrica | Ref | Modelo | Diferença | IC 95% | Só ref / só modelo | McNemar p |
|---|---|---|---|---|---|---|---|
| lora_v1 | campos/exato_livre | 56.4 | 69.2 | +12.8 | [+11.0, +14.6] | 65 / 407 | 1.49e-61 |
| lora_v1 | campos/exato_local | 55.8 | 69.2 | +13.3 | [+11.3, +15.2] | 65 / 420 | 1.2e-64 |
| lora_v1 | nomes/exato_livre | 40.4 | 44.5 | +4.1 | [+0.4, +7.6] | 22 / 42 | 0.0169 |
| lora_v1 | nomes/exato_local | 40.4 | 44.5 | +4.1 | [+0.4, +7.6] | 22 / 42 | 0.0169 |
| lora_v1 | completude | 85.0 | 92.8 | +7.8 | [+5.9, +9.8] | - | - |
| lora_v2 | campos/exato_livre | 56.4 | 72.0 | +15.7 | [+13.6, +17.9] | 74 / 492 | 1.02e-76 |
| lora_v2 | campos/exato_local | 55.8 | 72.0 | +16.2 | [+13.9, +18.6] | 73 / 505 | 1.91e-80 |
| lora_v2 | nomes/exato_livre | 40.4 | 50.2 | +9.8 | [+5.5, +14.7] | 26 / 74 | 1.67e-06 |
| lora_v2 | nomes/exato_local | 40.4 | 50.2 | +9.8 | [+5.5, +14.7] | 26 / 74 | 1.67e-06 |
| lora_v2 | completude | 85.0 | 93.1 | +8.1 | [+6.2, +10.5] | - | - |
| lora_v2_fp8 | campos/exato_livre | 56.4 | 71.9 | +15.5 | [+13.4, +17.7] | 66 / 480 | 1.39e-78 |
| lora_v2_fp8 | campos/exato_local | 55.8 | 71.9 | +16.0 | [+13.9, +18.3] | 66 / 494 | 4.99e-82 |
| lora_v2_fp8 | nomes/exato_livre | 40.4 | 49.6 | +9.2 | [+4.9, +14.3] | 27 / 72 | 6.9e-06 |
| lora_v2_fp8 | nomes/exato_local | 40.4 | 49.6 | +9.2 | [+4.9, +14.3] | 27 / 72 | 6.9e-06 |
| lora_v2_fp8 | completude | 85.0 | 92.8 | +7.8 | [+5.9, +10.0] | - | - |
| lora_v2_int4 | campos/exato_livre | 56.4 | 71.6 | +15.2 | [+13.0, +17.4] | 80 / 485 | 1.13e-71 |
| lora_v2_int4 | campos/exato_local | 55.8 | 71.6 | +15.7 | [+13.4, +18.1] | 79 / 498 | 2.7e-75 |
| lora_v2_int4 | nomes/exato_livre | 40.4 | 49.4 | +9.0 | [+4.6, +14.3] | 34 / 78 | 3.91e-05 |
| lora_v2_int4 | nomes/exato_local | 40.4 | 49.4 | +9.0 | [+4.6, +14.3] | 34 / 78 | 3.91e-05 |
| lora_v2_int4 | completude | 85.0 | 92.5 | +7.5 | [+5.6, +9.8] | - | - |

## Por template

| template | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| certidao_casamento | base_g4 | 13 | 77 | 50.6 | 50.6 | 26.9 | 96.2 | 0.0 | 0.0 |
| certidao_casamento | lora_v1 | 13 | 77 | 68.8 | 68.8 | 50.0 | 98.1 | 0.0 | 0.0 |
| certidao_casamento | lora_v2 | 13 | 77 | 71.4 | 71.4 | 50.0 | 98.1 | 0.0 | 0.0 |
| certidao_casamento | lora_v2_fp8 | 13 | 77 | 71.4 | 71.4 | 50.0 | 98.1 | 0.0 | 0.0 |
| certidao_casamento | lora_v2_int4 | 13 | 77 | 68.8 | 68.8 | 46.2 | 98.1 | 0.0 | 0.0 |
| certidao_casamento_cnj | base_g4 | 23 | 648 | 55.4 | 55.1 | 47.1 | 84.8 | 0.0 | 0.0 |
| certidao_casamento_cnj | lora_v1 | 23 | 648 | 65.6 | 65.4 | 51.7 | 90.4 | 0.0 | 0.0 |
| certidao_casamento_cnj | lora_v2 | 23 | 648 | 70.7 | 70.7 | 61.6 | 91.4 | 0.0 | 0.0 |
| certidao_casamento_cnj | lora_v2_fp8 | 23 | 648 | 70.2 | 70.2 | 61.0 | 90.9 | 0.0 | 0.0 |
| certidao_casamento_cnj | lora_v2_int4 | 23 | 648 | 70.2 | 70.2 | 63.4 | 89.8 | 0.0 | 0.0 |
| certidao_nascimento_cnj | base_g4 | 16 | 373 | 52.8 | 52.8 | 37.5 | 81.2 | 0.0 | 0.0 |
| certidao_nascimento_cnj | lora_v1 | 16 | 373 | 63.0 | 63.0 | 45.0 | 87.7 | 0.0 | 0.0 |
| certidao_nascimento_cnj | lora_v2 | 16 | 373 | 65.1 | 65.1 | 51.2 | 89.3 | 0.0 | 0.0 |
| certidao_nascimento_cnj | lora_v2_fp8 | 16 | 373 | 64.1 | 64.1 | 48.8 | 88.8 | 0.0 | 0.0 |
| certidao_nascimento_cnj | lora_v2_int4 | 16 | 373 | 63.5 | 63.5 | 46.2 | 88.0 | 0.0 | 0.0 |
| certidao_obito | base_g4 | 22 | 545 | 60.0 | 59.8 | 40.3 | 86.8 | 4.5 | 4.5 |
| certidao_obito | lora_v1 | 22 | 545 | 69.9 | 69.9 | 41.1 | 92.7 | 0.0 | 0.0 |
| certidao_obito | lora_v2 | 22 | 545 | 71.0 | 71.0 | 43.4 | 93.1 | 0.0 | 0.0 |
| certidao_obito | lora_v2_fp8 | 22 | 545 | 72.3 | 72.3 | 44.2 | 92.9 | 0.0 | 0.0 |
| certidao_obito | lora_v2_int4 | 22 | 545 | 71.6 | 71.6 | 44.2 | 92.3 | 0.0 | 0.0 |
| dnv | base_g4 | 26 | 1025 | 56.8 | 55.7 | 33.3 | 80.4 | 19.2 | 7.7 |
| dnv | lora_v1 | 26 | 1025 | 73.4 | 73.4 | 32.1 | 95.3 | 0.0 | 0.0 |
| dnv | lora_v2 | 26 | 1025 | 76.0 | 76.0 | 35.8 | 94.5 | 0.0 | 0.0 |
| dnv | lora_v2_fp8 | 26 | 1025 | 75.6 | 75.6 | 34.6 | 94.1 | 0.0 | 0.0 |
| dnv | lora_v2_int4 | 26 | 1025 | 75.5 | 75.5 | 32.1 | 95.1 | 0.0 | 0.0 |

## Por level

| level | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| 1 | base_g4 | 14 | 409 | 60.4 | 60.1 | 50.0 | 87.4 | 0.0 | 0.0 |
| 1 | lora_v1 | 14 | 409 | 75.8 | 75.8 | 51.4 | 95.2 | 0.0 | 0.0 |
| 1 | lora_v2 | 14 | 409 | 76.3 | 76.3 | 50.0 | 95.4 | 0.0 | 0.0 |
| 1 | lora_v2_fp8 | 14 | 409 | 76.8 | 76.8 | 52.7 | 94.9 | 0.0 | 0.0 |
| 1 | lora_v2_int4 | 14 | 409 | 74.6 | 74.6 | 52.7 | 94.3 | 0.0 | 0.0 |
| 2 | base_g4 | 33 | 909 | 54.7 | 54.2 | 35.8 | 84.1 | 12.1 | 6.1 |
| 2 | lora_v1 | 33 | 909 | 68.0 | 68.0 | 43.8 | 92.6 | 0.0 | 0.0 |
| 2 | lora_v2 | 33 | 909 | 71.0 | 71.0 | 46.9 | 93.3 | 0.0 | 0.0 |
| 2 | lora_v2_fp8 | 33 | 909 | 71.1 | 71.1 | 45.1 | 92.9 | 0.0 | 0.0 |
| 2 | lora_v2_int4 | 33 | 909 | 70.4 | 70.4 | 46.3 | 92.7 | 0.0 | 0.0 |
| 3 | base_g4 | 29 | 722 | 56.0 | 55.0 | 43.0 | 84.6 | 3.4 | 3.4 |
| 3 | lora_v1 | 29 | 722 | 70.1 | 69.9 | 47.7 | 92.7 | 0.0 | 0.0 |
| 3 | lora_v2 | 29 | 722 | 72.7 | 72.7 | 56.2 | 92.8 | 0.0 | 0.0 |
| 3 | lora_v2_fp8 | 29 | 722 | 72.4 | 72.4 | 56.2 | 92.4 | 0.0 | 0.0 |
| 3 | lora_v2_int4 | 29 | 722 | 72.0 | 72.0 | 53.1 | 92.0 | 0.0 | 0.0 |
| 4 | base_g4 | 24 | 628 | 56.7 | 56.4 | 37.9 | 85.3 | 4.2 | 0.0 |
| 4 | lora_v1 | 24 | 628 | 65.6 | 65.6 | 37.9 | 91.6 | 0.0 | 0.0 |
| 4 | lora_v2 | 24 | 628 | 70.1 | 70.1 | 48.4 | 91.8 | 0.0 | 0.0 |
| 4 | lora_v2_fp8 | 24 | 628 | 69.3 | 69.3 | 46.8 | 91.8 | 0.0 | 0.0 |
| 4 | lora_v2_int4 | 24 | 628 | 70.7 | 70.7 | 47.6 | 91.9 | 0.0 | 0.0 |

## Por split

| split | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| test | base_g4 | 100 | 2668 | 56.4 | 55.8 | 40.4 | 85.0 | 6.0 | 3.0 |
| test | lora_v1 | 100 | 2668 | 69.2 | 69.2 | 44.5 | 92.8 | 0.0 | 0.0 |
| test | lora_v2 | 100 | 2668 | 72.0 | 72.0 | 50.2 | 93.1 | 0.0 | 0.0 |
| test | lora_v2_fp8 | 100 | 2668 | 71.9 | 71.9 | 49.6 | 92.8 | 0.0 | 0.0 |
| test | lora_v2_int4 | 100 | 2668 | 71.6 | 71.6 | 49.4 | 92.5 | 0.0 | 0.0 |
