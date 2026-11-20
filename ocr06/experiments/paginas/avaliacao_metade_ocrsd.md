# Avaliação de páginas inteiras: metade_ocrsd

47 páginas com gabarito e predição de todos os modelos. 104 campos cuja tinta perdeu os acentos ficam de fora. Campos de até 3 caracteres vão para uma tabela à parte. Valores em %.

Livre: o valor pode estar em qualquer ponto da saída. Local: só nos blocos cuja caixa encosta na do campo. CER = distância de edição / tamanho do campo. Campos numéricos comparados só por letras e dígitos.

## Campos manuscritos

| Modelo | Campos | Exatos livre | CER livre | Exatos local | CER local | Nomes | Nomes exatos livre | Nomes exatos local | Nomes CER local |
|---|---|---|---|---|---|---|---|---|---|
| base | 726 | 84.7 | 2.0 | 84.7 | 2.3 | 196 | 83.7 | 83.7 | 1.8 |
| lora_v0 | 726 | 85.7 | 2.2 | 84.4 | 3.5 | 196 | 88.8 | 85.7 | 4.1 |

### Por classe de campo

| Classe | Modelo | Campos | Exatos livre | CER livre | Exatos local | CER local |
|---|---|---|---|---|---|---|
| closed | base | 123 | 78.0 | 7.1 | 78.0 | 8.8 |
| closed | lora_v0 | 123 | 74.8 | 7.8 | 74.0 | 13.1 |
| date | base | 48 | 97.9 | 0.1 | 97.9 | 0.1 |
| date | lora_v0 | 48 | 97.9 | 0.1 | 97.9 | 0.1 |
| name | base | 196 | 83.7 | 1.7 | 83.7 | 1.8 |
| name | lora_v0 | 196 | 88.8 | 2.2 | 85.7 | 4.1 |
| number | base | 156 | 98.1 | 0.2 | 98.1 | 0.2 |
| number | lora_v0 | 156 | 96.8 | 0.3 | 96.2 | 0.7 |
| place | base | 64 | 93.8 | 1.9 | 93.8 | 2.2 |
| place | lora_v0 | 64 | 89.1 | 3.7 | 87.5 | 5.4 |
| text | base | 139 | 68.3 | 1.6 | 68.3 | 1.7 |
| text | lora_v0 | 139 | 72.7 | 1.4 | 72.7 | 1.7 |

### Campos curtos (até 3 caracteres, fora dos totais)

| Modelo | Campos | Exatos livre | Exatos local |
|---|---|---|---|
| base | 238 | 97.5 | 95.8 |
| lora_v0 | 238 | 95.8 | 91.6 |

## Página

Completude: fração dos campos achados com CER <= 0.2 (livre). Truncada: `fim = length` ou últimos campos ausentes sem bloco na altura deles. Laço: trecho repetido em sequência (>= 100 caracteres, >= 3 vezes) ou saída >= 1.5x a dos outros modelos. Impresso: CER entre a saída do modelo e a da referência (base) depois de apagar os valores manuscritos.

| Modelo | Páginas | Completude | Truncadas | Laços | Impresso CER vs ref | Idem, sem maiúsc./minúsc. | Páginas com impresso alterado |
|---|---|---|---|---|---|---|---|
| base | 47 | 96.2 | 0.0 | 4.3 | - | - | - |
| lora_v0 | 47 | 94.4 | 0.0 | 0.0 | 15.75 | 12.31 | 95.7 |

## Comparação pareada com base

Diferença em pontos percentuais (modelo - referência) nas mesmas páginas e campos; IC de 95% por bootstrap pareado sobre páginas; McNemar exato campo a campo (só ref = acertos só da referência, só modelo = acertos só do modelo).

| Modelo | Métrica | Ref | Modelo | Diferença | IC 95% | Só ref / só modelo | McNemar p |
|---|---|---|---|---|---|---|---|
| lora_v0 | campos/exato_livre | 84.7 | 85.7 | +1.0 | [-2.5, +3.5] | 22 / 29 | 0.401 |
| lora_v0 | campos/exato_local | 84.7 | 84.4 | -0.3 | [-4.0, +2.5] | 31 / 29 | 0.897 |
| lora_v0 | nomes/exato_livre | 83.7 | 88.8 | +5.1 | [-0.5, +11.3] | 4 / 14 | 0.0309 |
| lora_v0 | nomes/exato_local | 83.7 | 85.7 | +2.0 | [-4.8, +9.0] | 10 / 14 | 0.541 |
| lora_v0 | completude | 96.2 | 94.4 | -1.9 | [-6.7, +0.9] | - | - |

## Por template

| template | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| certidao_casamento | base | 19 | 68 | 85.3 | 85.3 | 82.1 | 100.0 | 0.0 | 0.0 |
| certidao_casamento | lora_v0 | 19 | 68 | 85.3 | 85.3 | 82.1 | 100.0 | 0.0 | 0.0 |
| certidao_casamento_cnj | base | 14 | 431 | 89.1 | 89.1 | 88.8 | 98.8 | 0.0 | 0.0 |
| certidao_casamento_cnj | lora_v0 | 14 | 431 | 90.3 | 89.8 | 95.3 | 98.4 | 0.0 | 0.0 |
| certidao_nascimento_cnj | base | 4 | 38 | 78.9 | 78.9 | 76.9 | 95.6 | 0.0 | 0.0 |
| certidao_nascimento_cnj | lora_v0 | 4 | 38 | 78.9 | 78.9 | 69.2 | 94.3 | 0.0 | 0.0 |
| certidao_obito | base | 10 | 189 | 75.7 | 75.7 | 75.0 | 86.0 | 0.0 | 20.0 |
| certidao_obito | lora_v0 | 10 | 189 | 76.7 | 73.0 | 70.8 | 78.6 | 0.0 | 0.0 |

## Por writing

| writing | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| aaron1259 | base | 10 | 59 | 67.8 | 67.8 | 76.9 | 88.5 | 0.0 | 20.0 |
| aaron1259 | lora_v0 | 10 | 59 | 57.6 | 45.8 | 57.7 | 79.7 | 0.0 | 0.0 |
| font | base | 24 | 614 | 87.0 | 87.0 | 86.3 | 98.3 | 0.0 | 0.0 |
| font | lora_v0 | 24 | 614 | 89.1 | 88.8 | 93.2 | 98.6 | 0.0 | 0.0 |
| sjvasquez | base | 9 | 44 | 77.3 | 77.3 | 77.8 | 97.8 | 0.0 | 0.0 |
| sjvasquez | lora_v0 | 9 | 44 | 81.8 | 81.8 | 77.8 | 97.2 | 0.0 | 0.0 |
| wpvnteam | base | 4 | 9 | 77.8 | 77.8 | 66.7 | 100.0 | 0.0 | 0.0 |
| wpvnteam | lora_v0 | 4 | 9 | 55.6 | 55.6 | 50.0 | 100.0 | 0.0 | 0.0 |

## Por split

| split | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| test | base | 47 | 726 | 84.7 | 84.7 | 83.7 | 96.2 | 0.0 | 4.3 |
| test | lora_v0 | 47 | 726 | 85.7 | 84.4 | 85.7 | 94.4 | 0.0 | 0.0 |
