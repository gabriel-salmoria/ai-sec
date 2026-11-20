# Avaliação de páginas inteiras: forms_v2_normal

100 páginas com gabarito e predição de todos os modelos. 0 campos cuja tinta perdeu os acentos ficam de fora. Campos de até 3 caracteres vão para uma tabela à parte. Valores em %.

Livre: o valor pode estar em qualquer ponto da saída. Local: só nos blocos cuja caixa encosta na do campo. CER = distância de edição / tamanho do campo. Campos numéricos comparados só por letras e dígitos.

## Campos manuscritos

| Modelo | Campos | Exatos livre | CER livre | Exatos local | CER local | Nomes | Nomes exatos livre | Nomes exatos local | Nomes CER local |
|---|---|---|---|---|---|---|---|---|---|
| lora_v1 | 2668 | 69.2 | 5.4 | 69.2 | 5.4 | 488 | 44.5 | 44.5 | 7.5 |
| lora_v2 | 2668 | 72.0 | 5.0 | 72.0 | 5.0 | 488 | 50.2 | 50.2 | 7.1 |

### Por classe de campo

| Classe | Modelo | Campos | Exatos livre | CER livre | Exatos local | CER local |
|---|---|---|---|---|---|---|
| closed | lora_v1 | 519 | 84.0 | 1.9 | 84.0 | 2.1 |
| closed | lora_v2 | 519 | 85.0 | 1.5 | 85.0 | 1.7 |
| date | lora_v1 | 170 | 94.7 | 0.4 | 94.7 | 0.4 |
| date | lora_v2 | 170 | 96.5 | 0.3 | 96.5 | 0.3 |
| name | lora_v1 | 488 | 44.5 | 7.5 | 44.5 | 7.5 |
| name | lora_v2 | 488 | 50.2 | 7.1 | 50.2 | 7.1 |
| number | lora_v1 | 795 | 77.0 | 4.8 | 76.9 | 4.9 |
| number | lora_v2 | 795 | 80.8 | 3.8 | 80.8 | 3.8 |
| place | lora_v1 | 279 | 72.8 | 7.0 | 72.8 | 7.2 |
| place | lora_v2 | 279 | 70.3 | 8.1 | 70.3 | 8.2 |
| text | lora_v1 | 417 | 52.0 | 6.6 | 52.0 | 6.6 |
| text | lora_v2 | 417 | 56.1 | 6.2 | 56.1 | 6.2 |

### Campos curtos (até 3 caracteres, fora dos totais)

| Modelo | Campos | Exatos livre | Exatos local |
|---|---|---|---|
| lora_v1 | 1048 | 95.0 | 93.7 |
| lora_v2 | 1048 | 96.0 | 95.2 |

## Página

Completude: fração dos campos achados com CER <= 0.2 (livre). Truncada: `fim = length` ou últimos campos ausentes sem bloco na altura deles. Laço: trecho repetido em sequência (>= 100 caracteres, >= 3 vezes) ou saída >= 1.5x a dos outros modelos. Impresso: CER entre a saída do modelo e a da referência (lora_v1) depois de apagar os valores manuscritos.

| Modelo | Páginas | Completude | Truncadas | Laços | Impresso CER vs ref | Idem, sem maiúsc./minúsc. | Páginas com impresso alterado |
|---|---|---|---|---|---|---|---|
| lora_v1 | 100 | 92.8 | 0.0 | 0.0 | - | - | - |
| lora_v2 | 100 | 93.1 | 0.0 | 0.0 | 2.61 | 2.60 | 72.0 |

## Comparação pareada com lora_v1

Diferença em pontos percentuais (modelo - referência) nas mesmas páginas e campos; IC de 95% por bootstrap pareado sobre páginas; McNemar exato campo a campo (só ref = acertos só da referência, só modelo = acertos só do modelo).

| Modelo | Métrica | Ref | Modelo | Diferença | IC 95% | Só ref / só modelo | McNemar p |
|---|---|---|---|---|---|---|---|
| lora_v2 | campos/exato_livre | 69.2 | 72.0 | +2.8 | [+1.2, +4.5] | 68 / 144 | 1.94e-07 |
| lora_v2 | campos/exato_local | 69.2 | 72.0 | +2.9 | [+1.2, +4.5] | 68 / 145 | 1.42e-07 |
| lora_v2 | nomes/exato_livre | 44.5 | 50.2 | +5.7 | [+2.1, +10.0] | 13 / 41 | 0.000175 |
| lora_v2 | nomes/exato_local | 44.5 | 50.2 | +5.7 | [+2.1, +10.0] | 13 / 41 | 0.000175 |
| lora_v2 | completude | 92.8 | 93.1 | +0.4 | [-0.4, +1.2] | - | - |

## Por template

| template | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| certidao_casamento | lora_v1 | 13 | 77 | 68.8 | 68.8 | 50.0 | 98.1 | 0.0 | 0.0 |
| certidao_casamento | lora_v2 | 13 | 77 | 71.4 | 71.4 | 50.0 | 98.1 | 0.0 | 0.0 |
| certidao_casamento_cnj | lora_v1 | 23 | 648 | 65.6 | 65.4 | 51.7 | 90.4 | 0.0 | 0.0 |
| certidao_casamento_cnj | lora_v2 | 23 | 648 | 70.7 | 70.7 | 61.6 | 91.4 | 0.0 | 0.0 |
| certidao_nascimento_cnj | lora_v1 | 16 | 373 | 63.0 | 63.0 | 45.0 | 87.7 | 0.0 | 0.0 |
| certidao_nascimento_cnj | lora_v2 | 16 | 373 | 65.1 | 65.1 | 51.2 | 89.3 | 0.0 | 0.0 |
| certidao_obito | lora_v1 | 22 | 545 | 69.9 | 69.9 | 41.1 | 92.7 | 0.0 | 0.0 |
| certidao_obito | lora_v2 | 22 | 545 | 71.0 | 71.0 | 43.4 | 93.1 | 0.0 | 0.0 |
| dnv | lora_v1 | 26 | 1025 | 73.4 | 73.4 | 32.1 | 95.3 | 0.0 | 0.0 |
| dnv | lora_v2 | 26 | 1025 | 76.0 | 76.0 | 35.8 | 94.5 | 0.0 | 0.0 |

## Por level

| level | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| 1 | lora_v1 | 14 | 409 | 75.8 | 75.8 | 51.4 | 95.2 | 0.0 | 0.0 |
| 1 | lora_v2 | 14 | 409 | 76.3 | 76.3 | 50.0 | 95.4 | 0.0 | 0.0 |
| 2 | lora_v1 | 33 | 909 | 68.0 | 68.0 | 43.8 | 92.6 | 0.0 | 0.0 |
| 2 | lora_v2 | 33 | 909 | 71.0 | 71.0 | 46.9 | 93.3 | 0.0 | 0.0 |
| 3 | lora_v1 | 29 | 722 | 70.1 | 69.9 | 47.7 | 92.7 | 0.0 | 0.0 |
| 3 | lora_v2 | 29 | 722 | 72.7 | 72.7 | 56.2 | 92.8 | 0.0 | 0.0 |
| 4 | lora_v1 | 24 | 628 | 65.6 | 65.6 | 37.9 | 91.6 | 0.0 | 0.0 |
| 4 | lora_v2 | 24 | 628 | 70.1 | 70.1 | 48.4 | 91.8 | 0.0 | 0.0 |

## Por split

| split | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| test | lora_v1 | 100 | 2668 | 69.2 | 69.2 | 44.5 | 92.8 | 0.0 | 0.0 |
| test | lora_v2 | 100 | 2668 | 72.0 | 72.0 | 50.2 | 93.1 | 0.0 | 0.0 |
