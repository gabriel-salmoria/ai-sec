# Avaliação de páginas inteiras: teste_local

100 páginas com gabarito e predição de todos os modelos. 0 campos cuja tinta perdeu os acentos ficam de fora. Campos de até 3 caracteres vão para uma tabela à parte. Valores em %.

Livre: o valor pode estar em qualquer ponto da saída. Local: só nos blocos cuja caixa encosta na do campo. CER = distância de edição / tamanho do campo. Campos numéricos comparados só por letras e dígitos.

## Campos manuscritos

| Modelo | Campos | Exatos livre | CER livre | Exatos local | CER local | Nomes | Nomes exatos livre | Nomes exatos local | Nomes CER local |
|---|---|---|---|---|---|---|---|---|---|
| base_g4 | 2648 | 55.6 | 10.0 | 55.4 | 10.4 | 440 | 24.3 | 24.3 | 12.7 |
| base_fp8 | 2648 | 55.4 | 10.2 | 55.1 | 11.0 | 440 | 24.3 | 24.3 | 12.9 |
| lora_v1 | 2648 | 69.9 | 5.4 | 69.8 | 5.5 | 440 | 30.5 | 30.5 | 10.1 |
| lora_v2 | 2648 | 72.3 | 4.8 | 72.2 | 4.9 | 440 | 32.5 | 32.5 | 9.1 |
| lora_v2_fp8 | 2648 | 71.8 | 5.0 | 71.7 | 5.0 | 440 | 30.7 | 30.7 | 9.2 |
| lora_v2_int4 | 2648 | 70.0 | 5.4 | 69.9 | 5.5 | 440 | 28.9 | 28.9 | 9.8 |

### Por classe de campo

| Classe | Modelo | Campos | Exatos livre | CER livre | Exatos local | CER local |
|---|---|---|---|---|---|---|
| closed | base_g4 | 578 | 70.2 | 8.9 | 70.2 | 10.0 |
| closed | base_fp8 | 578 | 69.9 | 9.6 | 69.6 | 11.9 |
| closed | lora_v1 | 578 | 83.0 | 1.9 | 83.0 | 1.9 |
| closed | lora_v2 | 578 | 83.7 | 1.8 | 83.7 | 1.8 |
| closed | lora_v2_fp8 | 578 | 83.4 | 1.9 | 83.4 | 1.9 |
| closed | lora_v2_int4 | 578 | 83.4 | 2.0 | 83.4 | 2.0 |
| date | base_g4 | 133 | 75.2 | 3.1 | 75.2 | 3.2 |
| date | base_fp8 | 133 | 73.7 | 3.2 | 73.7 | 3.3 |
| date | lora_v1 | 133 | 88.0 | 1.1 | 88.0 | 1.1 |
| date | lora_v2 | 133 | 91.7 | 0.8 | 91.7 | 0.8 |
| date | lora_v2_fp8 | 133 | 91.7 | 0.8 | 91.7 | 0.8 |
| date | lora_v2_int4 | 133 | 91.0 | 0.8 | 91.0 | 0.8 |
| name | base_g4 | 440 | 24.3 | 12.4 | 24.3 | 12.7 |
| name | base_fp8 | 440 | 24.3 | 12.5 | 24.3 | 12.9 |
| name | lora_v1 | 440 | 30.5 | 10.0 | 30.5 | 10.1 |
| name | lora_v2 | 440 | 32.5 | 9.1 | 32.5 | 9.1 |
| name | lora_v2_fp8 | 440 | 30.7 | 9.2 | 30.7 | 9.2 |
| name | lora_v2_int4 | 440 | 28.9 | 9.7 | 28.9 | 9.8 |
| number | base_g4 | 844 | 59.8 | 10.4 | 59.8 | 10.7 |
| number | base_fp8 | 844 | 60.4 | 10.4 | 60.3 | 11.1 |
| number | lora_v1 | 844 | 82.5 | 3.2 | 82.5 | 3.2 |
| number | lora_v2 | 844 | 86.7 | 2.6 | 86.7 | 2.6 |
| number | lora_v2_fp8 | 844 | 85.4 | 2.8 | 85.4 | 2.9 |
| number | lora_v2_int4 | 844 | 84.2 | 3.1 | 84.2 | 3.2 |
| place | base_g4 | 286 | 67.8 | 8.1 | 66.8 | 9.0 |
| place | base_fp8 | 286 | 68.5 | 7.9 | 66.8 | 9.8 |
| place | lora_v1 | 286 | 74.8 | 6.2 | 73.8 | 6.9 |
| place | lora_v2 | 286 | 72.4 | 5.8 | 71.3 | 6.5 |
| place | lora_v2_fp8 | 286 | 73.8 | 6.2 | 72.7 | 6.9 |
| place | lora_v2_int4 | 286 | 67.1 | 7.3 | 66.1 | 8.2 |
| text | base_g4 | 367 | 43.3 | 10.3 | 42.8 | 10.4 |
| text | base_fp8 | 367 | 41.7 | 10.5 | 41.1 | 10.6 |
| text | lora_v1 | 367 | 57.5 | 5.9 | 57.5 | 5.9 |
| text | lora_v2 | 367 | 61.9 | 5.3 | 61.9 | 5.3 |
| text | lora_v2_fp8 | 367 | 62.9 | 5.4 | 62.9 | 5.5 |
| text | lora_v2_int4 | 367 | 59.9 | 6.0 | 59.9 | 6.0 |

### Campos curtos (até 3 caracteres, fora dos totais)

| Modelo | Campos | Exatos livre | Exatos local |
|---|---|---|---|
| base_g4 | 1081 | 91.8 | 89.3 |
| base_fp8 | 1081 | 90.6 | 88.3 |
| lora_v1 | 1081 | 95.5 | 94.9 |
| lora_v2 | 1081 | 96.5 | 96.2 |
| lora_v2_fp8 | 1081 | 96.7 | 96.3 |
| lora_v2_int4 | 1081 | 96.5 | 96.0 |

## Página

Completude: fração dos campos achados com CER <= 0.2 (livre). Truncada: `fim = length` ou últimos campos ausentes sem bloco na altura deles. Laço: trecho repetido em sequência (>= 100 caracteres, >= 3 vezes) ou saída >= 1.5x a dos outros modelos. Impresso: CER entre a saída do modelo e a da referência (base_g4) depois de apagar os valores manuscritos.

| Modelo | Páginas | Completude | Truncadas | Laços | Impresso CER vs ref | Idem, sem maiúsc./minúsc. | Páginas com impresso alterado |
|---|---|---|---|---|---|---|---|
| base_g4 | 100 | 84.6 | 1.0 | 1.0 | - | - | - |
| base_fp8 | 100 | 84.6 | 4.0 | 1.0 | 23.20 | 23.01 | 76.0 |
| lora_v1 | 100 | 92.6 | 0.0 | 0.0 | 26.32 | 26.08 | 100.0 |
| lora_v2 | 100 | 93.5 | 0.0 | 0.0 | 26.50 | 26.26 | 99.0 |
| lora_v2_fp8 | 100 | 92.9 | 0.0 | 0.0 | 26.50 | 26.26 | 99.0 |
| lora_v2_int4 | 100 | 91.9 | 0.0 | 0.0 | 26.72 | 26.48 | 99.0 |

## Comparação pareada com base_g4

Diferença em pontos percentuais (modelo - referência) nas mesmas páginas e campos; IC de 95% por bootstrap pareado sobre páginas; McNemar exato campo a campo (só ref = acertos só da referência, só modelo = acertos só do modelo).

| Modelo | Métrica | Ref | Modelo | Diferença | IC 95% | Só ref / só modelo | McNemar p |
|---|---|---|---|---|---|---|---|
| base_fp8 | campos/exato_livre | 55.6 | 55.4 | -0.1 | [-2.0, +1.6] | 77 / 74 | 0.871 |
| base_fp8 | campos/exato_local | 55.4 | 55.1 | -0.3 | [-2.3, +1.4] | 81 / 73 | 0.573 |
| base_fp8 | nomes/exato_livre | 24.3 | 24.3 | +0.0 | [-1.2, +1.3] | 4 / 4 | 1 |
| base_fp8 | nomes/exato_local | 24.3 | 24.3 | +0.0 | [-1.2, +1.3] | 4 / 4 | 1 |
| base_fp8 | completude | 84.6 | 84.6 | -0.0 | [-1.7, +1.5] | - | - |
| lora_v1 | campos/exato_livre | 55.6 | 69.9 | +14.4 | [+12.4, +16.5] | 48 / 429 | 1.49e-77 |
| lora_v1 | campos/exato_local | 55.4 | 69.8 | +14.5 | [+12.5, +16.6] | 48 / 431 | 4.6e-78 |
| lora_v1 | nomes/exato_livre | 24.3 | 30.5 | +6.1 | [+2.4, +10.2] | 14 / 41 | 0.000355 |
| lora_v1 | nomes/exato_local | 24.3 | 30.5 | +6.1 | [+2.4, +10.2] | 14 / 41 | 0.000355 |
| lora_v1 | completude | 84.6 | 92.6 | +7.9 | [+5.7, +10.7] | - | - |
| lora_v2 | campos/exato_livre | 55.6 | 72.3 | +16.8 | [+14.5, +19.2] | 54 / 498 | 5.24e-91 |
| lora_v2 | campos/exato_local | 55.4 | 72.2 | +16.8 | [+14.6, +19.3] | 54 / 500 | 1.61e-91 |
| lora_v2 | nomes/exato_livre | 24.3 | 32.5 | +8.2 | [+3.8, +12.6] | 16 / 52 | 1.41e-05 |
| lora_v2 | nomes/exato_local | 24.3 | 32.5 | +8.2 | [+3.8, +12.6] | 16 / 52 | 1.41e-05 |
| lora_v2 | completude | 84.6 | 93.5 | +8.9 | [+6.4, +11.5] | - | - |
| lora_v2_fp8 | campos/exato_livre | 55.6 | 71.8 | +16.3 | [+14.1, +18.8] | 54 / 485 | 1.11e-87 |
| lora_v2_fp8 | campos/exato_local | 55.4 | 71.7 | +16.4 | [+14.1, +18.9] | 54 / 487 | 3.43e-88 |
| lora_v2_fp8 | nomes/exato_livre | 24.3 | 30.7 | +6.4 | [+2.6, +10.2] | 16 / 44 | 0.000394 |
| lora_v2_fp8 | nomes/exato_local | 24.3 | 30.7 | +6.4 | [+2.6, +10.2] | 16 / 44 | 0.000394 |
| lora_v2_fp8 | completude | 84.6 | 92.9 | +8.3 | [+5.9, +10.9] | - | - |
| lora_v2_int4 | campos/exato_livre | 55.6 | 70.0 | +14.4 | [+12.3, +17.1] | 77 / 459 | 3.31e-67 |
| lora_v2_int4 | campos/exato_local | 55.4 | 69.9 | +14.5 | [+12.3, +17.1] | 77 / 461 | 1.13e-67 |
| lora_v2_int4 | nomes/exato_livre | 24.3 | 28.9 | +4.5 | [+1.2, +8.1] | 21 / 41 | 0.0151 |
| lora_v2_int4 | nomes/exato_local | 24.3 | 28.9 | +4.5 | [+1.2, +8.1] | 21 / 41 | 0.0151 |
| lora_v2_int4 | completude | 84.6 | 91.9 | +7.3 | [+4.9, +9.9] | - | - |

## Por template

| template | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| certidao_casamento | base_g4 | 16 | 91 | 48.4 | 48.4 | 25.0 | 92.5 | 0.0 | 0.0 |
| certidao_casamento | base_fp8 | 16 | 91 | 48.4 | 48.4 | 25.0 | 91.2 | 0.0 | 0.0 |
| certidao_casamento | lora_v1 | 16 | 91 | 58.2 | 58.2 | 28.1 | 95.0 | 0.0 | 0.0 |
| certidao_casamento | lora_v2 | 16 | 91 | 62.6 | 62.6 | 31.2 | 93.8 | 0.0 | 0.0 |
| certidao_casamento | lora_v2_fp8 | 16 | 91 | 61.5 | 61.5 | 31.2 | 93.8 | 0.0 | 0.0 |
| certidao_casamento | lora_v2_int4 | 16 | 91 | 61.5 | 61.5 | 28.1 | 93.8 | 0.0 | 0.0 |
| certidao_casamento_cnj | base_g4 | 17 | 473 | 49.7 | 49.5 | 25.4 | 81.5 | 0.0 | 0.0 |
| certidao_casamento_cnj | base_fp8 | 17 | 473 | 49.5 | 49.0 | 24.6 | 82.0 | 0.0 | 0.0 |
| certidao_casamento_cnj | lora_v1 | 17 | 473 | 63.8 | 63.8 | 35.4 | 91.3 | 0.0 | 0.0 |
| certidao_casamento_cnj | lora_v2 | 17 | 473 | 66.8 | 66.8 | 41.5 | 93.4 | 0.0 | 0.0 |
| certidao_casamento_cnj | lora_v2_fp8 | 17 | 473 | 65.3 | 65.3 | 37.7 | 92.2 | 0.0 | 0.0 |
| certidao_casamento_cnj | lora_v2_int4 | 17 | 473 | 62.6 | 62.6 | 34.6 | 89.7 | 0.0 | 0.0 |
| certidao_nascimento_cnj | base_g4 | 16 | 351 | 50.1 | 49.0 | 23.8 | 86.8 | 0.0 | 0.0 |
| certidao_nascimento_cnj | base_fp8 | 16 | 351 | 52.1 | 51.0 | 26.2 | 87.6 | 0.0 | 0.0 |
| certidao_nascimento_cnj | lora_v1 | 16 | 351 | 59.0 | 58.1 | 28.7 | 89.2 | 0.0 | 0.0 |
| certidao_nascimento_cnj | lora_v2 | 16 | 351 | 61.5 | 60.7 | 30.0 | 92.5 | 0.0 | 0.0 |
| certidao_nascimento_cnj | lora_v2_fp8 | 16 | 351 | 63.0 | 62.1 | 28.7 | 91.7 | 0.0 | 0.0 |
| certidao_nascimento_cnj | lora_v2_int4 | 16 | 351 | 59.5 | 58.7 | 28.7 | 89.1 | 0.0 | 0.0 |
| certidao_obito | base_g4 | 16 | 383 | 54.0 | 54.0 | 28.6 | 82.9 | 6.2 | 6.2 |
| certidao_obito | base_fp8 | 16 | 383 | 53.5 | 53.5 | 28.6 | 83.5 | 0.0 | 0.0 |
| certidao_obito | lora_v1 | 16 | 383 | 64.8 | 64.8 | 29.7 | 88.9 | 0.0 | 0.0 |
| certidao_obito | lora_v2 | 16 | 383 | 68.9 | 68.9 | 29.7 | 90.4 | 0.0 | 0.0 |
| certidao_obito | lora_v2_fp8 | 16 | 383 | 68.7 | 68.7 | 28.6 | 89.4 | 0.0 | 0.0 |
| certidao_obito | lora_v2_int4 | 16 | 383 | 67.6 | 67.6 | 26.4 | 90.3 | 0.0 | 0.0 |
| dnv | base_g4 | 35 | 1350 | 59.9 | 59.9 | 19.6 | 82.4 | 0.0 | 0.0 |
| dnv | base_fp8 | 35 | 1350 | 59.4 | 59.1 | 18.7 | 81.9 | 11.4 | 2.9 |
| dnv | lora_v1 | 35 | 1350 | 77.2 | 77.2 | 27.1 | 95.4 | 0.0 | 0.0 |
| dnv | lora_v2 | 35 | 1350 | 78.7 | 78.7 | 26.2 | 95.4 | 0.0 | 0.0 |
| dnv | lora_v2_fp8 | 35 | 1350 | 78.0 | 78.0 | 25.2 | 95.0 | 0.0 | 0.0 |
| dnv | lora_v2_int4 | 35 | 1350 | 76.5 | 76.5 | 24.3 | 94.2 | 0.0 | 0.0 |

## Por level

| level | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| 1 | base_g4 | 26 | 694 | 56.3 | 56.3 | 23.1 | 88.8 | 0.0 | 0.0 |
| 1 | base_fp8 | 26 | 694 | 56.3 | 55.9 | 21.4 | 90.1 | 3.8 | 0.0 |
| 1 | lora_v1 | 26 | 694 | 69.3 | 69.3 | 31.6 | 94.0 | 0.0 | 0.0 |
| 1 | lora_v2 | 26 | 694 | 70.5 | 70.5 | 29.1 | 94.9 | 0.0 | 0.0 |
| 1 | lora_v2_fp8 | 26 | 694 | 69.7 | 69.7 | 28.2 | 94.3 | 0.0 | 0.0 |
| 1 | lora_v2_int4 | 26 | 694 | 66.9 | 66.9 | 24.8 | 92.6 | 0.0 | 0.0 |
| 2 | base_g4 | 33 | 922 | 58.4 | 57.8 | 24.5 | 85.3 | 0.0 | 0.0 |
| 2 | base_fp8 | 33 | 922 | 56.4 | 55.6 | 25.9 | 83.8 | 6.1 | 3.0 |
| 2 | lora_v1 | 33 | 922 | 74.0 | 73.6 | 30.2 | 96.0 | 0.0 | 0.0 |
| 2 | lora_v2 | 33 | 922 | 77.8 | 77.4 | 34.5 | 97.1 | 0.0 | 0.0 |
| 2 | lora_v2_fp8 | 33 | 922 | 76.9 | 76.6 | 29.5 | 96.5 | 0.0 | 0.0 |
| 2 | lora_v2_int4 | 33 | 922 | 75.8 | 75.5 | 30.2 | 95.8 | 0.0 | 0.0 |
| 3 | base_g4 | 25 | 705 | 55.3 | 55.3 | 27.4 | 84.3 | 4.0 | 4.0 |
| 3 | base_fp8 | 25 | 705 | 57.7 | 57.7 | 28.2 | 85.2 | 0.0 | 0.0 |
| 3 | lora_v1 | 25 | 705 | 70.2 | 70.2 | 35.0 | 91.0 | 0.0 | 0.0 |
| 3 | lora_v2 | 25 | 705 | 71.2 | 71.2 | 35.9 | 91.2 | 0.0 | 0.0 |
| 3 | lora_v2_fp8 | 25 | 705 | 70.8 | 70.8 | 35.9 | 91.1 | 0.0 | 0.0 |
| 3 | lora_v2_int4 | 25 | 705 | 69.4 | 69.4 | 32.5 | 90.0 | 0.0 | 0.0 |
| 4 | base_g4 | 16 | 327 | 46.5 | 46.5 | 20.9 | 76.9 | 0.0 | 0.0 |
| 4 | base_fp8 | 16 | 327 | 45.9 | 45.9 | 19.4 | 76.2 | 6.2 | 0.0 |
| 4 | lora_v1 | 16 | 327 | 59.3 | 59.3 | 20.9 | 85.7 | 0.0 | 0.0 |
| 4 | lora_v2 | 16 | 327 | 63.3 | 63.3 | 28.4 | 87.5 | 0.0 | 0.0 |
| 4 | lora_v2_fp8 | 16 | 327 | 64.2 | 64.2 | 28.4 | 86.3 | 0.0 | 0.0 |
| 4 | lora_v2_int4 | 16 | 327 | 61.5 | 61.5 | 26.9 | 85.8 | 0.0 | 0.0 |

## Por split

| split | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| test | base_g4 | 100 | 2648 | 55.6 | 55.4 | 24.3 | 84.6 | 1.0 | 1.0 |
| test | base_fp8 | 100 | 2648 | 55.4 | 55.1 | 24.3 | 84.6 | 4.0 | 1.0 |
| test | lora_v1 | 100 | 2648 | 69.9 | 69.8 | 30.5 | 92.6 | 0.0 | 0.0 |
| test | lora_v2 | 100 | 2648 | 72.3 | 72.2 | 32.5 | 93.5 | 0.0 | 0.0 |
| test | lora_v2_fp8 | 100 | 2648 | 71.8 | 71.7 | 30.7 | 92.9 | 0.0 | 0.0 |
| test | lora_v2_int4 | 100 | 2648 | 70.0 | 69.9 | 28.9 | 91.9 | 0.0 | 0.0 |
