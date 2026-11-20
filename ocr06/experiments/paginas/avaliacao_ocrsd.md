# Avaliação de páginas inteiras: ocrsd

50 páginas com gabarito e predição de todos os modelos (predições sem gabarito ignoradas: base 30, ft 30). 27 campos cuja tinta perdeu os acentos ficam de fora. Campos de até 3 caracteres vão para uma tabela à parte. Valores em %.

Livre: o valor pode estar em qualquer ponto da saída. Local: só nos blocos cuja caixa encosta na do campo. CER = distância de edição / tamanho do campo. Campos numéricos comparados só por letras e dígitos.

## Campos manuscritos

| Modelo | Campos | Exatos livre | CER livre | Exatos local | CER local | Nomes | Nomes exatos livre | Nomes exatos local | Nomes CER local |
|---|---|---|---|---|---|---|---|---|---|
| base | 769 | 89.1 | 0.7 | 89.1 | 0.8 | 172 | 88.4 | 88.4 | 0.9 |
| ft | 769 | 90.6 | 0.6 | 90.5 | 0.7 | 172 | 90.7 | 90.1 | 0.6 |

### Por classe de campo

| Classe | Modelo | Campos | Exatos livre | CER livre | Exatos local | CER local |
|---|---|---|---|---|---|---|
| closed | base | 79 | 64.6 | 6.7 | 64.6 | 7.0 |
| closed | ft | 79 | 69.6 | 6.8 | 69.6 | 7.4 |
| date | base | 80 | 98.8 | 0.1 | 98.8 | 0.1 |
| date | ft | 80 | 100.0 | 0.0 | 100.0 | 0.0 |
| name | base | 172 | 88.4 | 0.9 | 88.4 | 0.9 |
| name | ft | 172 | 90.7 | 0.6 | 90.1 | 0.6 |
| number | base | 179 | 97.8 | 0.2 | 97.8 | 0.2 |
| number | ft | 179 | 96.1 | 0.4 | 96.1 | 0.4 |
| place | base | 60 | 95.0 | 0.5 | 95.0 | 0.5 |
| place | ft | 60 | 95.0 | 0.9 | 95.0 | 0.9 |
| text | base | 199 | 85.9 | 0.4 | 85.9 | 0.4 |
| text | ft | 199 | 88.9 | 0.3 | 88.9 | 0.3 |

### Campos curtos (até 3 caracteres, fora dos totais)

| Modelo | Campos | Exatos livre | Exatos local |
|---|---|---|---|
| base | 265 | 96.2 | 96.2 |
| ft | 265 | 96.6 | 96.6 |

## Página

Completude: fração dos campos achados com CER <= 0.2 (livre). Truncada: `fim = length` ou últimos campos ausentes sem bloco na altura deles. Laço: trecho repetido em sequência (>= 100 caracteres, >= 3 vezes) ou saída >= 1.5x a dos outros modelos. Impresso: CER entre a saída do modelo e a da referência (base) depois de apagar os valores manuscritos.

| Modelo | Páginas | Completude | Truncadas | Laços | Impresso CER vs ref | Idem, sem maiúsc./minúsc. | Páginas com impresso alterado |
|---|---|---|---|---|---|---|---|
| base | 50 | 96.7 | 0.0 | 0.0 | - | - | - |
| ft | 50 | 98.7 | 0.0 | 0.0 | 7.90 | 2.56 | 88.0 |

## Comparação pareada com base

Diferença em pontos percentuais (modelo - referência) nas mesmas páginas e campos; IC de 95% por bootstrap pareado sobre páginas; McNemar exato campo a campo (só ref = acertos só da referência, só modelo = acertos só do modelo).

| Modelo | Métrica | Ref | Modelo | Diferença | IC 95% | Só ref / só modelo | McNemar p |
|---|---|---|---|---|---|---|---|
| ft | campos/exato_livre | 89.1 | 90.6 | +1.6 | [+0.0, +3.1] | 14 / 26 | 0.0807 |
| ft | campos/exato_local | 89.1 | 90.5 | +1.4 | [-0.3, +3.0] | 15 / 26 | 0.117 |
| ft | nomes/exato_livre | 88.4 | 90.7 | +2.3 | [-1.6, +6.4] | 2 / 6 | 0.289 |
| ft | nomes/exato_local | 88.4 | 90.1 | +1.7 | [-2.4, +5.8] | 3 / 6 | 0.508 |
| ft | completude | 96.7 | 98.7 | +2.0 | [-0.7, +6.3] | - | - |

## Por template

| template | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| certidao_casamento | base | 30 | 197 | 86.8 | 86.8 | 83.0 | 95.7 | 0.0 | 0.0 |
| certidao_casamento | ft | 30 | 197 | 85.8 | 85.3 | 84.9 | 98.8 | 0.0 | 0.0 |
| certidao_obito | base | 20 | 572 | 89.9 | 89.9 | 90.8 | 98.1 | 0.0 | 0.0 |
| certidao_obito | ft | 20 | 572 | 92.3 | 92.3 | 92.4 | 98.6 | 0.0 | 0.0 |

## Por writing

| writing | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| font | base | 40 | 753 | 89.2 | 89.2 | 89.3 | 98.4 | 0.0 | 0.0 |
| font | ft | 40 | 753 | 90.7 | 90.6 | 90.6 | 98.4 | 0.0 | 0.0 |
| sjvasquez | base | 10 | 16 | 81.2 | 81.2 | 76.9 | 88.9 | 0.0 | 0.0 |
| sjvasquez | ft | 10 | 16 | 87.5 | 87.5 | 84.6 | 100.0 | 0.0 | 0.0 |

## Por split

| split | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| test | base | 11 | 283 | 82.3 | 82.3 | 84.7 | 96.1 | 0.0 | 0.0 |
| test | ft | 11 | 283 | 86.9 | 86.9 | 91.5 | 97.5 | 0.0 | 0.0 |
| train | base | 39 | 486 | 93.0 | 93.0 | 90.3 | 96.8 | 0.0 | 0.0 |
| train | ft | 39 | 486 | 92.8 | 92.6 | 89.4 | 99.0 | 0.0 | 0.0 |
