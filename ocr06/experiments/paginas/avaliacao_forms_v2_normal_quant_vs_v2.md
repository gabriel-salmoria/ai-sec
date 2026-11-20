# Avaliação de páginas inteiras: forms_v2_normal

100 páginas com gabarito e predição de todos os modelos. 0 campos cuja tinta perdeu os acentos ficam de fora. Campos de até 3 caracteres vão para uma tabela à parte. Valores em %.

Livre: o valor pode estar em qualquer ponto da saída. Local: só nos blocos cuja caixa encosta na do campo. CER = distância de edição / tamanho do campo. Campos numéricos comparados só por letras e dígitos.

## Campos manuscritos

| Modelo | Campos | Exatos livre | CER livre | Exatos local | CER local | Nomes | Nomes exatos livre | Nomes exatos local | Nomes CER local |
|---|---|---|---|---|---|---|---|---|---|
| lora_v2 | 2668 | 72.0 | 5.0 | 72.0 | 5.0 | 488 | 50.2 | 50.2 | 7.1 |
| lora_v2_fp8 | 2668 | 71.9 | 5.1 | 71.9 | 5.1 | 488 | 49.6 | 49.6 | 7.1 |
| lora_v2_int4 | 2668 | 71.6 | 5.2 | 71.6 | 5.2 | 488 | 49.4 | 49.4 | 7.3 |

### Por classe de campo

| Classe | Modelo | Campos | Exatos livre | CER livre | Exatos local | CER local |
|---|---|---|---|---|---|---|
| closed | lora_v2 | 519 | 85.0 | 1.5 | 85.0 | 1.7 |
| closed | lora_v2_fp8 | 519 | 85.0 | 1.5 | 85.0 | 1.7 |
| closed | lora_v2_int4 | 519 | 85.0 | 1.7 | 85.0 | 1.8 |
| date | lora_v2 | 170 | 96.5 | 0.3 | 96.5 | 0.3 |
| date | lora_v2_fp8 | 170 | 95.9 | 0.4 | 95.9 | 0.4 |
| date | lora_v2_int4 | 170 | 95.3 | 0.3 | 95.3 | 0.3 |
| name | lora_v2 | 488 | 50.2 | 7.1 | 50.2 | 7.1 |
| name | lora_v2_fp8 | 488 | 49.6 | 7.1 | 49.6 | 7.1 |
| name | lora_v2_int4 | 488 | 49.4 | 7.3 | 49.4 | 7.3 |
| number | lora_v2 | 795 | 80.8 | 3.8 | 80.8 | 3.8 |
| number | lora_v2_fp8 | 795 | 79.4 | 4.1 | 79.4 | 4.2 |
| number | lora_v2_int4 | 795 | 79.2 | 4.3 | 79.2 | 4.3 |
| place | lora_v2 | 279 | 70.3 | 8.1 | 70.3 | 8.2 |
| place | lora_v2_fp8 | 279 | 73.1 | 7.9 | 73.1 | 8.0 |
| place | lora_v2_int4 | 279 | 71.0 | 8.1 | 71.0 | 8.5 |
| text | lora_v2 | 417 | 56.1 | 6.2 | 56.1 | 6.2 |
| text | lora_v2_fp8 | 417 | 56.8 | 6.3 | 56.8 | 6.3 |
| text | lora_v2_int4 | 417 | 56.8 | 6.2 | 56.8 | 6.2 |

### Campos curtos (até 3 caracteres, fora dos totais)

| Modelo | Campos | Exatos livre | Exatos local |
|---|---|---|---|
| lora_v2 | 1048 | 96.0 | 95.2 |
| lora_v2_fp8 | 1048 | 95.7 | 94.8 |
| lora_v2_int4 | 1048 | 95.6 | 94.9 |

## Página

Completude: fração dos campos achados com CER <= 0.2 (livre). Truncada: `fim = length` ou últimos campos ausentes sem bloco na altura deles. Laço: trecho repetido em sequência (>= 100 caracteres, >= 3 vezes) ou saída >= 1.5x a dos outros modelos. Impresso: CER entre a saída do modelo e a da referência (lora_v2) depois de apagar os valores manuscritos.

| Modelo | Páginas | Completude | Truncadas | Laços | Impresso CER vs ref | Idem, sem maiúsc./minúsc. | Páginas com impresso alterado |
|---|---|---|---|---|---|---|---|
| lora_v2 | 100 | 93.1 | 0.0 | 0.0 | - | - | - |
| lora_v2_fp8 | 100 | 92.8 | 0.0 | 0.0 | 1.14 | 1.13 | 34.0 |
| lora_v2_int4 | 100 | 92.5 | 0.0 | 0.0 | 2.08 | 2.07 | 62.0 |

## Comparação pareada com lora_v2

Diferença em pontos percentuais (modelo - referência) nas mesmas páginas e campos; IC de 95% por bootstrap pareado sobre páginas; McNemar exato campo a campo (só ref = acertos só da referência, só modelo = acertos só do modelo).

| Modelo | Métrica | Ref | Modelo | Diferença | IC 95% | Só ref / só modelo | McNemar p |
|---|---|---|---|---|---|---|---|
| lora_v2_fp8 | campos/exato_livre | 72.0 | 71.9 | -0.1 | [-0.9, +0.6] | 27 / 23 | 0.672 |
| lora_v2_fp8 | campos/exato_local | 72.0 | 71.9 | -0.1 | [-0.9, +0.6] | 27 / 23 | 0.672 |
| lora_v2_fp8 | nomes/exato_livre | 50.2 | 49.6 | -0.6 | [-1.7, +0.4] | 5 / 2 | 0.453 |
| lora_v2_fp8 | nomes/exato_local | 50.2 | 49.6 | -0.6 | [-1.7, +0.4] | 5 / 2 | 0.453 |
| lora_v2_fp8 | completude | 93.1 | 92.8 | -0.3 | [-0.7, +0.0] | - | - |
| lora_v2_int4 | campos/exato_livre | 72.0 | 71.6 | -0.5 | [-1.7, +0.7] | 60 / 47 | 0.246 |
| lora_v2_int4 | campos/exato_local | 72.0 | 71.6 | -0.5 | [-1.7, +0.7] | 60 / 47 | 0.246 |
| lora_v2_int4 | nomes/exato_livre | 50.2 | 49.4 | -0.8 | [-4.3, +3.0] | 20 / 16 | 0.618 |
| lora_v2_int4 | nomes/exato_local | 50.2 | 49.4 | -0.8 | [-4.3, +3.0] | 20 / 16 | 0.618 |
| lora_v2_int4 | completude | 93.1 | 92.5 | -0.6 | [-1.3, +0.1] | - | - |

## Por template

| template | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| certidao_casamento | lora_v2 | 13 | 77 | 71.4 | 71.4 | 50.0 | 98.1 | 0.0 | 0.0 |
| certidao_casamento | lora_v2_fp8 | 13 | 77 | 71.4 | 71.4 | 50.0 | 98.1 | 0.0 | 0.0 |
| certidao_casamento | lora_v2_int4 | 13 | 77 | 68.8 | 68.8 | 46.2 | 98.1 | 0.0 | 0.0 |
| certidao_casamento_cnj | lora_v2 | 23 | 648 | 70.7 | 70.7 | 61.6 | 91.4 | 0.0 | 0.0 |
| certidao_casamento_cnj | lora_v2_fp8 | 23 | 648 | 70.2 | 70.2 | 61.0 | 90.9 | 0.0 | 0.0 |
| certidao_casamento_cnj | lora_v2_int4 | 23 | 648 | 70.2 | 70.2 | 63.4 | 89.8 | 0.0 | 0.0 |
| certidao_nascimento_cnj | lora_v2 | 16 | 373 | 65.1 | 65.1 | 51.2 | 89.3 | 0.0 | 0.0 |
| certidao_nascimento_cnj | lora_v2_fp8 | 16 | 373 | 64.1 | 64.1 | 48.8 | 88.8 | 0.0 | 0.0 |
| certidao_nascimento_cnj | lora_v2_int4 | 16 | 373 | 63.5 | 63.5 | 46.2 | 88.0 | 0.0 | 0.0 |
| certidao_obito | lora_v2 | 22 | 545 | 71.0 | 71.0 | 43.4 | 93.1 | 0.0 | 0.0 |
| certidao_obito | lora_v2_fp8 | 22 | 545 | 72.3 | 72.3 | 44.2 | 92.9 | 0.0 | 0.0 |
| certidao_obito | lora_v2_int4 | 22 | 545 | 71.6 | 71.6 | 44.2 | 92.3 | 0.0 | 0.0 |
| dnv | lora_v2 | 26 | 1025 | 76.0 | 76.0 | 35.8 | 94.5 | 0.0 | 0.0 |
| dnv | lora_v2_fp8 | 26 | 1025 | 75.6 | 75.6 | 34.6 | 94.1 | 0.0 | 0.0 |
| dnv | lora_v2_int4 | 26 | 1025 | 75.5 | 75.5 | 32.1 | 95.1 | 0.0 | 0.0 |

## Por level

| level | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| 1 | lora_v2 | 14 | 409 | 76.3 | 76.3 | 50.0 | 95.4 | 0.0 | 0.0 |
| 1 | lora_v2_fp8 | 14 | 409 | 76.8 | 76.8 | 52.7 | 94.9 | 0.0 | 0.0 |
| 1 | lora_v2_int4 | 14 | 409 | 74.6 | 74.6 | 52.7 | 94.3 | 0.0 | 0.0 |
| 2 | lora_v2 | 33 | 909 | 71.0 | 71.0 | 46.9 | 93.3 | 0.0 | 0.0 |
| 2 | lora_v2_fp8 | 33 | 909 | 71.1 | 71.1 | 45.1 | 92.9 | 0.0 | 0.0 |
| 2 | lora_v2_int4 | 33 | 909 | 70.4 | 70.4 | 46.3 | 92.7 | 0.0 | 0.0 |
| 3 | lora_v2 | 29 | 722 | 72.7 | 72.7 | 56.2 | 92.8 | 0.0 | 0.0 |
| 3 | lora_v2_fp8 | 29 | 722 | 72.4 | 72.4 | 56.2 | 92.4 | 0.0 | 0.0 |
| 3 | lora_v2_int4 | 29 | 722 | 72.0 | 72.0 | 53.1 | 92.0 | 0.0 | 0.0 |
| 4 | lora_v2 | 24 | 628 | 70.1 | 70.1 | 48.4 | 91.8 | 0.0 | 0.0 |
| 4 | lora_v2_fp8 | 24 | 628 | 69.3 | 69.3 | 46.8 | 91.8 | 0.0 | 0.0 |
| 4 | lora_v2_int4 | 24 | 628 | 70.7 | 70.7 | 47.6 | 91.9 | 0.0 | 0.0 |

## Por split

| split | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| test | lora_v2 | 100 | 2668 | 72.0 | 72.0 | 50.2 | 93.1 | 0.0 | 0.0 |
| test | lora_v2_fp8 | 100 | 2668 | 71.9 | 71.9 | 49.6 | 92.8 | 0.0 | 0.0 |
| test | lora_v2_int4 | 100 | 2668 | 71.6 | 71.6 | 49.4 | 92.5 | 0.0 | 0.0 |
