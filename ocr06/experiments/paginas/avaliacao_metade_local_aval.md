# Avaliação de páginas inteiras: metade_local_aval

38 páginas com gabarito e predição de todos os modelos (predições sem gabarito ignoradas: base 9, lora_v0 9). 0 campos cuja tinta perdeu os acentos ficam de fora. Campos de até 3 caracteres vão para uma tabela à parte. Valores em %.

Livre: o valor pode estar em qualquer ponto da saída. Local: só nos blocos cuja caixa encosta na do campo. CER = distância de edição / tamanho do campo. Campos numéricos comparados só por letras e dígitos.

## Campos manuscritos

| Modelo | Campos | Exatos livre | CER livre | Exatos local | CER local | Nomes | Nomes exatos livre | Nomes exatos local | Nomes CER local |
|---|---|---|---|---|---|---|---|---|---|
| base | 1068 | 56.6 | 9.4 | 56.6 | 9.5 | 176 | 19.9 | 19.9 | 12.3 |
| lora_v0 | 1068 | 55.4 | 12.5 | 55.4 | 13.6 | 176 | 22.7 | 22.7 | 17.4 |

### Por classe de campo

| Classe | Modelo | Campos | Exatos livre | CER livre | Exatos local | CER local |
|---|---|---|---|---|---|---|
| closed | base | 241 | 70.1 | 7.5 | 70.1 | 7.8 |
| closed | lora_v0 | 241 | 67.2 | 8.6 | 67.2 | 10.3 |
| date | base | 50 | 84.0 | 2.1 | 84.0 | 2.2 |
| date | lora_v0 | 50 | 78.0 | 6.6 | 78.0 | 7.6 |
| name | base | 176 | 19.9 | 12.2 | 19.9 | 12.3 |
| name | lora_v0 | 176 | 22.7 | 16.2 | 22.7 | 17.4 |
| number | base | 342 | 63.7 | 10.1 | 63.7 | 10.1 |
| number | lora_v0 | 342 | 60.8 | 12.9 | 60.8 | 13.0 |
| place | base | 115 | 67.8 | 6.2 | 67.8 | 6.3 |
| place | lora_v0 | 115 | 71.3 | 7.3 | 71.3 | 8.4 |
| text | base | 144 | 43.1 | 10.2 | 43.1 | 10.3 |
| text | lora_v0 | 144 | 42.4 | 14.7 | 42.4 | 15.7 |

### Campos curtos (até 3 caracteres, fora dos totais)

| Modelo | Campos | Exatos livre | Exatos local |
|---|---|---|---|
| base | 440 | 92.7 | 91.8 |
| lora_v0 | 440 | 89.1 | 88.9 |

## Página

Completude: fração dos campos achados com CER <= 0.2 (livre). Truncada: `fim = length` ou últimos campos ausentes sem bloco na altura deles. Laço: trecho repetido em sequência (>= 100 caracteres, >= 3 vezes) ou saída >= 1.5x a dos outros modelos. Impresso: CER entre a saída do modelo e a da referência (base) depois de apagar os valores manuscritos.

| Modelo | Páginas | Completude | Truncadas | Laços | Impresso CER vs ref | Idem, sem maiúsc./minúsc. | Páginas com impresso alterado |
|---|---|---|---|---|---|---|---|
| base | 38 | 85.7 | 0.0 | 5.3 | - | - | - |
| lora_v0 | 38 | 81.5 | 2.6 | 0.0 | 28.94 | 28.24 | 100.0 |

## Comparação pareada com base

Diferença em pontos percentuais (modelo - referência) nas mesmas páginas e campos; IC de 95% por bootstrap pareado sobre páginas; McNemar exato campo a campo (só ref = acertos só da referência, só modelo = acertos só do modelo).

| Modelo | Métrica | Ref | Modelo | Diferença | IC 95% | Só ref / só modelo | McNemar p |
|---|---|---|---|---|---|---|---|
| lora_v0 | campos/exato_livre | 56.6 | 55.4 | -1.1 | [-5.8, +2.7] | 83 / 71 | 0.375 |
| lora_v0 | campos/exato_local | 56.6 | 55.4 | -1.1 | [-5.8, +2.7] | 83 / 71 | 0.375 |
| lora_v0 | nomes/exato_livre | 19.9 | 22.7 | +2.8 | [-6.3, +11.8] | 8 / 13 | 0.383 |
| lora_v0 | nomes/exato_local | 19.9 | 22.7 | +2.8 | [-6.3, +11.8] | 8 / 13 | 0.383 |
| lora_v0 | completude | 85.7 | 81.5 | -4.3 | [-10.0, +0.2] | - | - |

## Por template

| template | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| certidao_casamento | base | 4 | 20 | 45.0 | 45.0 | 12.5 | 85.0 | 0.0 | 0.0 |
| certidao_casamento | lora_v0 | 4 | 20 | 40.0 | 40.0 | 12.5 | 80.0 | 0.0 | 0.0 |
| certidao_casamento_cnj | base | 8 | 224 | 46.0 | 46.0 | 9.4 | 83.6 | 0.0 | 25.0 |
| certidao_casamento_cnj | lora_v0 | 8 | 224 | 44.6 | 44.6 | 14.1 | 70.0 | 12.5 | 0.0 |
| certidao_nascimento_cnj | base | 6 | 128 | 53.1 | 53.1 | 30.0 | 88.3 | 0.0 | 0.0 |
| certidao_nascimento_cnj | lora_v0 | 6 | 128 | 55.5 | 55.5 | 40.0 | 85.9 | 0.0 | 0.0 |
| certidao_obito | base | 5 | 118 | 63.6 | 63.6 | 20.7 | 94.2 | 0.0 | 0.0 |
| certidao_obito | lora_v0 | 5 | 118 | 61.0 | 61.0 | 17.2 | 90.7 | 0.0 | 0.0 |
| dnv | base | 15 | 578 | 60.4 | 60.4 | 28.9 | 83.2 | 0.0 | 0.0 |
| dnv | lora_v0 | 15 | 578 | 59.0 | 59.0 | 28.9 | 83.1 | 0.0 | 0.0 |

## Por level

| level | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| 1 | base | 12 | 357 | 58.5 | 58.5 | 22.7 | 89.6 | 0.0 | 8.3 |
| 1 | lora_v0 | 12 | 357 | 56.3 | 56.3 | 25.8 | 81.1 | 0.0 | 0.0 |
| 2 | base | 13 | 334 | 59.9 | 59.9 | 26.5 | 90.8 | 0.0 | 0.0 |
| 2 | lora_v0 | 13 | 334 | 61.4 | 61.4 | 28.6 | 91.6 | 0.0 | 0.0 |
| 3 | base | 9 | 265 | 51.7 | 51.7 | 13.3 | 80.2 | 0.0 | 11.1 |
| 3 | lora_v0 | 9 | 265 | 47.2 | 47.2 | 17.8 | 71.7 | 11.1 | 0.0 |
| 4 | base | 4 | 112 | 51.8 | 51.8 | 6.2 | 69.9 | 0.0 | 0.0 |
| 4 | lora_v0 | 4 | 112 | 54.5 | 54.5 | 6.2 | 71.8 | 0.0 | 0.0 |

## Por split

| split | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| test | base | 38 | 1068 | 56.6 | 56.6 | 19.9 | 85.7 | 0.0 | 5.3 |
| test | lora_v0 | 38 | 1068 | 55.4 | 55.4 | 22.7 | 81.5 | 2.6 | 0.0 |
