# Avaliação de páginas inteiras: teste_local

100 páginas com gabarito e predição de todos os modelos. 0 campos cuja tinta perdeu os acentos ficam de fora. Campos de até 3 caracteres vão para uma tabela à parte. Valores em %.

Livre: o valor pode estar em qualquer ponto da saída. Local: só nos blocos cuja caixa encosta na do campo. CER = distância de edição / tamanho do campo. Campos numéricos comparados só por letras e dígitos.

## Campos manuscritos

| Modelo | Campos | Exatos livre | CER livre | Exatos local | CER local | Nomes | Nomes exatos livre | Nomes exatos local | Nomes CER local |
|---|---|---|---|---|---|---|---|---|---|
| lora_v1 | 2648 | 69.9 | 5.4 | 69.8 | 5.5 | 440 | 30.5 | 30.5 | 10.1 |
| lora_v2 | 2648 | 72.3 | 4.8 | 72.2 | 4.9 | 440 | 32.5 | 32.5 | 9.1 |

### Por classe de campo

| Classe | Modelo | Campos | Exatos livre | CER livre | Exatos local | CER local |
|---|---|---|---|---|---|---|
| closed | lora_v1 | 578 | 83.0 | 1.9 | 83.0 | 1.9 |
| closed | lora_v2 | 578 | 83.7 | 1.8 | 83.7 | 1.8 |
| date | lora_v1 | 133 | 88.0 | 1.1 | 88.0 | 1.1 |
| date | lora_v2 | 133 | 91.7 | 0.8 | 91.7 | 0.8 |
| name | lora_v1 | 440 | 30.5 | 10.0 | 30.5 | 10.1 |
| name | lora_v2 | 440 | 32.5 | 9.1 | 32.5 | 9.1 |
| number | lora_v1 | 844 | 82.5 | 3.2 | 82.5 | 3.2 |
| number | lora_v2 | 844 | 86.7 | 2.6 | 86.7 | 2.6 |
| place | lora_v1 | 286 | 74.8 | 6.2 | 73.8 | 6.9 |
| place | lora_v2 | 286 | 72.4 | 5.8 | 71.3 | 6.5 |
| text | lora_v1 | 367 | 57.5 | 5.9 | 57.5 | 5.9 |
| text | lora_v2 | 367 | 61.9 | 5.3 | 61.9 | 5.3 |

### Campos curtos (até 3 caracteres, fora dos totais)

| Modelo | Campos | Exatos livre | Exatos local |
|---|---|---|---|
| lora_v1 | 1081 | 95.5 | 94.9 |
| lora_v2 | 1081 | 96.5 | 96.2 |

## Página

Completude: fração dos campos achados com CER <= 0.2 (livre). Truncada: `fim = length` ou últimos campos ausentes sem bloco na altura deles. Laço: trecho repetido em sequência (>= 100 caracteres, >= 3 vezes) ou saída >= 1.5x a dos outros modelos. Impresso: CER entre a saída do modelo e a da referência (lora_v1) depois de apagar os valores manuscritos.

| Modelo | Páginas | Completude | Truncadas | Laços | Impresso CER vs ref | Idem, sem maiúsc./minúsc. | Páginas com impresso alterado |
|---|---|---|---|---|---|---|---|
| lora_v1 | 100 | 92.6 | 0.0 | 0.0 | - | - | - |
| lora_v2 | 100 | 93.5 | 0.0 | 0.0 | 1.48 | 1.47 | 64.0 |

## Comparação pareada com lora_v1

Diferença em pontos percentuais (modelo - referência) nas mesmas páginas e campos; IC de 95% por bootstrap pareado sobre páginas; McNemar exato campo a campo (só ref = acertos só da referência, só modelo = acertos só do modelo).

| Modelo | Métrica | Ref | Modelo | Diferença | IC 95% | Só ref / só modelo | McNemar p |
|---|---|---|---|---|---|---|---|
| lora_v2 | campos/exato_livre | 69.9 | 72.3 | +2.4 | [+0.6, +4.1] | 65 / 128 | 6.77e-06 |
| lora_v2 | campos/exato_local | 69.8 | 72.2 | +2.4 | [+0.6, +4.1] | 65 / 128 | 6.77e-06 |
| lora_v2 | nomes/exato_livre | 30.5 | 32.5 | +2.0 | [-1.9, +6.8] | 15 / 24 | 0.2 |
| lora_v2 | nomes/exato_local | 30.5 | 32.5 | +2.0 | [-1.9, +6.8] | 15 / 24 | 0.2 |
| lora_v2 | completude | 92.6 | 93.5 | +0.9 | [-0.1, +2.0] | - | - |

## Por template

| template | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| certidao_casamento | lora_v1 | 16 | 91 | 58.2 | 58.2 | 28.1 | 95.0 | 0.0 | 0.0 |
| certidao_casamento | lora_v2 | 16 | 91 | 62.6 | 62.6 | 31.2 | 93.8 | 0.0 | 0.0 |
| certidao_casamento_cnj | lora_v1 | 17 | 473 | 63.8 | 63.8 | 35.4 | 91.3 | 0.0 | 0.0 |
| certidao_casamento_cnj | lora_v2 | 17 | 473 | 66.8 | 66.8 | 41.5 | 93.4 | 0.0 | 0.0 |
| certidao_nascimento_cnj | lora_v1 | 16 | 351 | 59.0 | 58.1 | 28.7 | 89.2 | 0.0 | 0.0 |
| certidao_nascimento_cnj | lora_v2 | 16 | 351 | 61.5 | 60.7 | 30.0 | 92.5 | 0.0 | 0.0 |
| certidao_obito | lora_v1 | 16 | 383 | 64.8 | 64.8 | 29.7 | 88.9 | 0.0 | 0.0 |
| certidao_obito | lora_v2 | 16 | 383 | 68.9 | 68.9 | 29.7 | 90.4 | 0.0 | 0.0 |
| dnv | lora_v1 | 35 | 1350 | 77.2 | 77.2 | 27.1 | 95.4 | 0.0 | 0.0 |
| dnv | lora_v2 | 35 | 1350 | 78.7 | 78.7 | 26.2 | 95.4 | 0.0 | 0.0 |

## Por level

| level | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| 1 | lora_v1 | 26 | 694 | 69.3 | 69.3 | 31.6 | 94.0 | 0.0 | 0.0 |
| 1 | lora_v2 | 26 | 694 | 70.5 | 70.5 | 29.1 | 94.9 | 0.0 | 0.0 |
| 2 | lora_v1 | 33 | 922 | 74.0 | 73.6 | 30.2 | 96.0 | 0.0 | 0.0 |
| 2 | lora_v2 | 33 | 922 | 77.8 | 77.4 | 34.5 | 97.1 | 0.0 | 0.0 |
| 3 | lora_v1 | 25 | 705 | 70.2 | 70.2 | 35.0 | 91.0 | 0.0 | 0.0 |
| 3 | lora_v2 | 25 | 705 | 71.2 | 71.2 | 35.9 | 91.2 | 0.0 | 0.0 |
| 4 | lora_v1 | 16 | 327 | 59.3 | 59.3 | 20.9 | 85.7 | 0.0 | 0.0 |
| 4 | lora_v2 | 16 | 327 | 63.3 | 63.3 | 28.4 | 87.5 | 0.0 | 0.0 |

## Por split

| split | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| test | lora_v1 | 100 | 2648 | 69.9 | 69.8 | 30.5 | 92.6 | 0.0 | 0.0 |
| test | lora_v2 | 100 | 2648 | 72.3 | 72.2 | 32.5 | 93.5 | 0.0 | 0.0 |
