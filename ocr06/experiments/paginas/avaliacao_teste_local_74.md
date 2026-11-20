# Avaliação de páginas inteiras: teste_local_74

74 páginas com gabarito e predição de todos os modelos (predições sem gabarito ignoradas: base 20). 0 campos cuja tinta perdeu os acentos ficam de fora. Campos de até 3 caracteres vão para uma tabela à parte. Valores em %.

Livre: o valor pode estar em qualquer ponto da saída. Local: só nos blocos cuja caixa encosta na do campo. CER = distância de edição / tamanho do campo. Campos numéricos comparados só por letras e dígitos.

## Campos manuscritos

| Modelo | Campos | Exatos livre | CER livre | Exatos local | CER local | Nomes | Nomes exatos livre | Nomes exatos local | Nomes CER local |
|---|---|---|---|---|---|---|---|---|---|
| base | 1963 | 57.6 | 9.5 | 57.3 | 9.8 | 331 | 25.1 | 25.1 | 12.3 |
| lora_v1 | 1963 | 71.4 | 5.0 | 71.2 | 5.1 | 331 | 31.1 | 31.1 | 9.4 |

### Por classe de campo

| Classe | Modelo | Campos | Exatos livre | CER livre | Exatos local | CER local |
|---|---|---|---|---|---|---|
| closed | base | 429 | 72.0 | 7.4 | 72.0 | 8.3 |
| closed | lora_v1 | 429 | 83.9 | 1.8 | 83.9 | 1.8 |
| date | base | 98 | 78.6 | 3.1 | 78.6 | 3.3 |
| date | lora_v1 | 98 | 91.8 | 0.9 | 91.8 | 0.9 |
| name | base | 331 | 25.1 | 12.0 | 25.1 | 12.3 |
| name | lora_v1 | 331 | 31.1 | 9.3 | 31.1 | 9.4 |
| number | base | 627 | 64.9 | 9.3 | 64.8 | 9.5 |
| number | lora_v1 | 627 | 86.9 | 2.2 | 86.9 | 2.2 |
| place | base | 213 | 66.2 | 8.2 | 64.8 | 9.1 |
| place | lora_v1 | 213 | 73.7 | 6.7 | 72.3 | 7.5 |
| text | base | 265 | 42.6 | 10.4 | 42.3 | 10.5 |
| text | lora_v1 | 265 | 55.1 | 5.8 | 55.1 | 5.8 |

### Campos curtos (até 3 caracteres, fora dos totais)

| Modelo | Campos | Exatos livre | Exatos local |
|---|---|---|---|
| base | 801 | 91.9 | 90.1 |
| lora_v1 | 801 | 95.5 | 95.0 |

## Página

Completude: fração dos campos achados com CER <= 0.2 (livre). Truncada: `fim = length` ou últimos campos ausentes sem bloco na altura deles. Laço: trecho repetido em sequência (>= 100 caracteres, >= 3 vezes) ou saída >= 1.5x a dos outros modelos. Impresso: CER entre a saída do modelo e a da referência (base) depois de apagar os valores manuscritos.

| Modelo | Páginas | Completude | Truncadas | Laços | Impresso CER vs ref | Idem, sem maiúsc./minúsc. | Páginas com impresso alterado |
|---|---|---|---|---|---|---|---|
| base | 74 | 86.3 | 0.0 | 0.0 | - | - | - |
| lora_v1 | 74 | 93.3 | 0.0 | 1.4 | 22.71 | 22.48 | 100.0 |

## Comparação pareada com base

Diferença em pontos percentuais (modelo - referência) nas mesmas páginas e campos; IC de 95% por bootstrap pareado sobre páginas; McNemar exato campo a campo (só ref = acertos só da referência, só modelo = acertos só do modelo).

| Modelo | Métrica | Ref | Modelo | Diferença | IC 95% | Só ref / só modelo | McNemar p |
|---|---|---|---|---|---|---|---|
| lora_v1 | campos/exato_livre | 57.6 | 71.4 | +13.8 | [+11.2, +16.4] | 35 / 306 | 3.54e-55 |
| lora_v1 | campos/exato_local | 57.3 | 71.2 | +13.9 | [+11.3, +16.5] | 35 / 308 | 1.1e-55 |
| lora_v1 | nomes/exato_livre | 25.1 | 31.1 | +6.0 | [+1.9, +11.4] | 13 / 33 | 0.00453 |
| lora_v1 | nomes/exato_local | 25.1 | 31.1 | +6.0 | [+1.9, +11.4] | 13 / 33 | 0.00453 |
| lora_v1 | completude | 86.3 | 93.3 | +6.9 | [+4.4, +10.3] | - | - |

## Por template

| template | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| certidao_casamento | base | 11 | 59 | 54.2 | 54.2 | 27.3 | 94.5 | 0.0 | 0.0 |
| certidao_casamento | lora_v1 | 11 | 59 | 61.0 | 61.0 | 31.8 | 96.4 | 0.0 | 0.0 |
| certidao_casamento_cnj | base | 14 | 390 | 51.3 | 51.0 | 24.8 | 82.5 | 0.0 | 0.0 |
| certidao_casamento_cnj | lora_v1 | 14 | 390 | 66.2 | 66.2 | 36.7 | 92.7 | 0.0 | 7.1 |
| certidao_nascimento_cnj | base | 12 | 261 | 47.5 | 46.0 | 20.0 | 84.5 | 0.0 | 0.0 |
| certidao_nascimento_cnj | lora_v1 | 12 | 261 | 55.6 | 54.4 | 25.0 | 86.3 | 0.0 | 0.0 |
| certidao_obito | base | 11 | 256 | 62.1 | 62.1 | 30.6 | 91.3 | 0.0 | 0.0 |
| certidao_obito | lora_v1 | 11 | 256 | 69.1 | 69.1 | 30.6 | 92.4 | 0.0 | 0.0 |
| dnv | base | 26 | 997 | 61.7 | 61.7 | 24.4 | 83.7 | 0.0 | 0.0 |
| dnv | lora_v1 | 26 | 997 | 78.7 | 78.7 | 28.2 | 95.9 | 0.0 | 0.0 |

## Por level

| level | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| 1 | base | 17 | 493 | 60.6 | 60.4 | 26.7 | 89.1 | 0.0 | 0.0 |
| 1 | lora_v1 | 17 | 493 | 73.4 | 73.4 | 36.0 | 94.5 | 0.0 | 0.0 |
| 2 | base | 26 | 694 | 59.9 | 59.4 | 27.8 | 86.7 | 0.0 | 0.0 |
| 2 | lora_v1 | 26 | 694 | 74.9 | 74.5 | 31.5 | 96.6 | 0.0 | 3.8 |
| 3 | base | 21 | 578 | 55.9 | 55.9 | 26.0 | 85.5 | 0.0 | 0.0 |
| 3 | lora_v1 | 21 | 578 | 69.4 | 69.4 | 33.0 | 90.5 | 0.0 | 0.0 |
| 4 | base | 10 | 198 | 46.5 | 46.5 | 10.8 | 82.5 | 0.0 | 0.0 |
| 4 | lora_v1 | 10 | 198 | 59.6 | 59.6 | 13.5 | 88.3 | 0.0 | 0.0 |

## Por split

| split | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| test | base | 74 | 1963 | 57.6 | 57.3 | 25.1 | 86.3 | 0.0 | 0.0 |
| test | lora_v1 | 74 | 1963 | 71.4 | 71.2 | 31.1 | 93.3 | 0.0 | 1.4 |
