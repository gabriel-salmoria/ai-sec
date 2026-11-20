# Avaliação de páginas inteiras: teste_local

100 páginas com gabarito e predição de todos os modelos. 0 campos cuja tinta perdeu os acentos ficam de fora. Campos de até 3 caracteres vão para uma tabela à parte. Valores em %.

Livre: o valor pode estar em qualquer ponto da saída. Local: só nos blocos cuja caixa encosta na do campo. CER = distância de edição / tamanho do campo. Campos numéricos comparados só por letras e dígitos.

## Campos manuscritos

| Modelo | Campos | Exatos livre | CER livre | Exatos local | CER local | Nomes | Nomes exatos livre | Nomes exatos local | Nomes CER local |
|---|---|---|---|---|---|---|---|---|---|
| lora_v2 | 2648 | 72.3 | 4.8 | 72.2 | 4.9 | 440 | 32.5 | 32.5 | 9.1 |
| lora_v2_fp8 | 2648 | 71.8 | 5.0 | 71.7 | 5.0 | 440 | 30.7 | 30.7 | 9.2 |
| lora_v2_int4 | 2648 | 70.0 | 5.4 | 69.9 | 5.5 | 440 | 28.9 | 28.9 | 9.8 |

### Por classe de campo

| Classe | Modelo | Campos | Exatos livre | CER livre | Exatos local | CER local |
|---|---|---|---|---|---|---|
| closed | lora_v2 | 578 | 83.7 | 1.8 | 83.7 | 1.8 |
| closed | lora_v2_fp8 | 578 | 83.4 | 1.9 | 83.4 | 1.9 |
| closed | lora_v2_int4 | 578 | 83.4 | 2.0 | 83.4 | 2.0 |
| date | lora_v2 | 133 | 91.7 | 0.8 | 91.7 | 0.8 |
| date | lora_v2_fp8 | 133 | 91.7 | 0.8 | 91.7 | 0.8 |
| date | lora_v2_int4 | 133 | 91.0 | 0.8 | 91.0 | 0.8 |
| name | lora_v2 | 440 | 32.5 | 9.1 | 32.5 | 9.1 |
| name | lora_v2_fp8 | 440 | 30.7 | 9.2 | 30.7 | 9.2 |
| name | lora_v2_int4 | 440 | 28.9 | 9.7 | 28.9 | 9.8 |
| number | lora_v2 | 844 | 86.7 | 2.6 | 86.7 | 2.6 |
| number | lora_v2_fp8 | 844 | 85.4 | 2.8 | 85.4 | 2.9 |
| number | lora_v2_int4 | 844 | 84.2 | 3.1 | 84.2 | 3.2 |
| place | lora_v2 | 286 | 72.4 | 5.8 | 71.3 | 6.5 |
| place | lora_v2_fp8 | 286 | 73.8 | 6.2 | 72.7 | 6.9 |
| place | lora_v2_int4 | 286 | 67.1 | 7.3 | 66.1 | 8.2 |
| text | lora_v2 | 367 | 61.9 | 5.3 | 61.9 | 5.3 |
| text | lora_v2_fp8 | 367 | 62.9 | 5.4 | 62.9 | 5.5 |
| text | lora_v2_int4 | 367 | 59.9 | 6.0 | 59.9 | 6.0 |

### Campos curtos (até 3 caracteres, fora dos totais)

| Modelo | Campos | Exatos livre | Exatos local |
|---|---|---|---|
| lora_v2 | 1081 | 96.5 | 96.2 |
| lora_v2_fp8 | 1081 | 96.7 | 96.3 |
| lora_v2_int4 | 1081 | 96.5 | 96.0 |

## Página

Completude: fração dos campos achados com CER <= 0.2 (livre). Truncada: `fim = length` ou últimos campos ausentes sem bloco na altura deles. Laço: trecho repetido em sequência (>= 100 caracteres, >= 3 vezes) ou saída >= 1.5x a dos outros modelos. Impresso: CER entre a saída do modelo e a da referência (lora_v2) depois de apagar os valores manuscritos.

| Modelo | Páginas | Completude | Truncadas | Laços | Impresso CER vs ref | Idem, sem maiúsc./minúsc. | Páginas com impresso alterado |
|---|---|---|---|---|---|---|---|
| lora_v2 | 100 | 93.5 | 0.0 | 0.0 | - | - | - |
| lora_v2_fp8 | 100 | 92.9 | 0.0 | 0.0 | 0.70 | 0.70 | 35.0 |
| lora_v2_int4 | 100 | 91.9 | 0.0 | 0.0 | 2.17 | 2.16 | 64.0 |

## Comparação pareada com lora_v2

Diferença em pontos percentuais (modelo - referência) nas mesmas páginas e campos; IC de 95% por bootstrap pareado sobre páginas; McNemar exato campo a campo (só ref = acertos só da referência, só modelo = acertos só do modelo).

| Modelo | Métrica | Ref | Modelo | Diferença | IC 95% | Só ref / só modelo | McNemar p |
|---|---|---|---|---|---|---|---|
| lora_v2_fp8 | campos/exato_livre | 72.3 | 71.8 | -0.5 | [-1.3, +0.3] | 26 / 13 | 0.0533 |
| lora_v2_fp8 | campos/exato_local | 72.2 | 71.7 | -0.5 | [-1.3, +0.3] | 26 / 13 | 0.0533 |
| lora_v2_fp8 | nomes/exato_livre | 32.5 | 30.7 | -1.8 | [-4.5, +0.0] | 9 / 1 | 0.0215 |
| lora_v2_fp8 | nomes/exato_local | 32.5 | 30.7 | -1.8 | [-4.5, +0.0] | 9 / 1 | 0.0215 |
| lora_v2_fp8 | completude | 93.5 | 92.9 | -0.6 | [-1.1, -0.2] | - | - |
| lora_v2_int4 | campos/exato_livre | 72.3 | 70.0 | -2.3 | [-3.4, -1.3] | 88 / 26 | 4.59e-09 |
| lora_v2_int4 | campos/exato_local | 72.2 | 69.9 | -2.3 | [-3.4, -1.3] | 88 / 26 | 4.59e-09 |
| lora_v2_int4 | nomes/exato_livre | 32.5 | 28.9 | -3.6 | [-7.0, -0.7] | 20 / 4 | 0.00154 |
| lora_v2_int4 | nomes/exato_local | 32.5 | 28.9 | -3.6 | [-7.0, -0.7] | 20 / 4 | 0.00154 |
| lora_v2_int4 | completude | 93.5 | 91.9 | -1.6 | [-2.6, -0.8] | - | - |

## Por template

| template | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| certidao_casamento | lora_v2 | 16 | 91 | 62.6 | 62.6 | 31.2 | 93.8 | 0.0 | 0.0 |
| certidao_casamento | lora_v2_fp8 | 16 | 91 | 61.5 | 61.5 | 31.2 | 93.8 | 0.0 | 0.0 |
| certidao_casamento | lora_v2_int4 | 16 | 91 | 61.5 | 61.5 | 28.1 | 93.8 | 0.0 | 0.0 |
| certidao_casamento_cnj | lora_v2 | 17 | 473 | 66.8 | 66.8 | 41.5 | 93.4 | 0.0 | 0.0 |
| certidao_casamento_cnj | lora_v2_fp8 | 17 | 473 | 65.3 | 65.3 | 37.7 | 92.2 | 0.0 | 0.0 |
| certidao_casamento_cnj | lora_v2_int4 | 17 | 473 | 62.6 | 62.6 | 34.6 | 89.7 | 0.0 | 0.0 |
| certidao_nascimento_cnj | lora_v2 | 16 | 351 | 61.5 | 60.7 | 30.0 | 92.5 | 0.0 | 0.0 |
| certidao_nascimento_cnj | lora_v2_fp8 | 16 | 351 | 63.0 | 62.1 | 28.7 | 91.7 | 0.0 | 0.0 |
| certidao_nascimento_cnj | lora_v2_int4 | 16 | 351 | 59.5 | 58.7 | 28.7 | 89.1 | 0.0 | 0.0 |
| certidao_obito | lora_v2 | 16 | 383 | 68.9 | 68.9 | 29.7 | 90.4 | 0.0 | 0.0 |
| certidao_obito | lora_v2_fp8 | 16 | 383 | 68.7 | 68.7 | 28.6 | 89.4 | 0.0 | 0.0 |
| certidao_obito | lora_v2_int4 | 16 | 383 | 67.6 | 67.6 | 26.4 | 90.3 | 0.0 | 0.0 |
| dnv | lora_v2 | 35 | 1350 | 78.7 | 78.7 | 26.2 | 95.4 | 0.0 | 0.0 |
| dnv | lora_v2_fp8 | 35 | 1350 | 78.0 | 78.0 | 25.2 | 95.0 | 0.0 | 0.0 |
| dnv | lora_v2_int4 | 35 | 1350 | 76.5 | 76.5 | 24.3 | 94.2 | 0.0 | 0.0 |

## Por level

| level | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| 1 | lora_v2 | 26 | 694 | 70.5 | 70.5 | 29.1 | 94.9 | 0.0 | 0.0 |
| 1 | lora_v2_fp8 | 26 | 694 | 69.7 | 69.7 | 28.2 | 94.3 | 0.0 | 0.0 |
| 1 | lora_v2_int4 | 26 | 694 | 66.9 | 66.9 | 24.8 | 92.6 | 0.0 | 0.0 |
| 2 | lora_v2 | 33 | 922 | 77.8 | 77.4 | 34.5 | 97.1 | 0.0 | 0.0 |
| 2 | lora_v2_fp8 | 33 | 922 | 76.9 | 76.6 | 29.5 | 96.5 | 0.0 | 0.0 |
| 2 | lora_v2_int4 | 33 | 922 | 75.8 | 75.5 | 30.2 | 95.8 | 0.0 | 0.0 |
| 3 | lora_v2 | 25 | 705 | 71.2 | 71.2 | 35.9 | 91.2 | 0.0 | 0.0 |
| 3 | lora_v2_fp8 | 25 | 705 | 70.8 | 70.8 | 35.9 | 91.1 | 0.0 | 0.0 |
| 3 | lora_v2_int4 | 25 | 705 | 69.4 | 69.4 | 32.5 | 90.0 | 0.0 | 0.0 |
| 4 | lora_v2 | 16 | 327 | 63.3 | 63.3 | 28.4 | 87.5 | 0.0 | 0.0 |
| 4 | lora_v2_fp8 | 16 | 327 | 64.2 | 64.2 | 28.4 | 86.3 | 0.0 | 0.0 |
| 4 | lora_v2_int4 | 16 | 327 | 61.5 | 61.5 | 26.9 | 85.8 | 0.0 | 0.0 |

## Por split

| split | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| test | lora_v2 | 100 | 2648 | 72.3 | 72.2 | 32.5 | 93.5 | 0.0 | 0.0 |
| test | lora_v2_fp8 | 100 | 2648 | 71.8 | 71.7 | 30.7 | 92.9 | 0.0 | 0.0 |
| test | lora_v2_int4 | 100 | 2648 | 70.0 | 69.9 | 28.9 | 91.9 | 0.0 | 0.0 |
