# Avaliação de páginas inteiras: teste_local

100 páginas com gabarito e predição de todos os modelos. 0 campos cuja tinta perdeu os acentos ficam de fora. Campos de até 3 caracteres vão para uma tabela à parte. Valores em %.

Livre: o valor pode estar em qualquer ponto da saída. Local: só nos blocos cuja caixa encosta na do campo. CER = distância de edição / tamanho do campo. Campos numéricos comparados só por letras e dígitos.

## Campos manuscritos

| Modelo | Campos | Exatos livre | CER livre | Exatos local | CER local | Nomes | Nomes exatos livre | Nomes exatos local | Nomes CER local |
|---|---|---|---|---|---|---|---|---|---|
| base_g4 | 2648 | 55.6 | 10.0 | 55.4 | 10.4 | 440 | 24.3 | 24.3 | 12.7 |
| lora_v1 | 2648 | 69.9 | 5.4 | 69.8 | 5.5 | 440 | 30.5 | 30.5 | 10.1 |
| lora_v2 | 2648 | 72.3 | 4.8 | 72.2 | 4.9 | 440 | 32.5 | 32.5 | 9.1 |

### Por classe de campo

| Classe | Modelo | Campos | Exatos livre | CER livre | Exatos local | CER local |
|---|---|---|---|---|---|---|
| closed | base_g4 | 578 | 70.2 | 8.9 | 70.2 | 10.0 |
| closed | lora_v1 | 578 | 83.0 | 1.9 | 83.0 | 1.9 |
| closed | lora_v2 | 578 | 83.7 | 1.8 | 83.7 | 1.8 |
| date | base_g4 | 133 | 75.2 | 3.1 | 75.2 | 3.2 |
| date | lora_v1 | 133 | 88.0 | 1.1 | 88.0 | 1.1 |
| date | lora_v2 | 133 | 91.7 | 0.8 | 91.7 | 0.8 |
| name | base_g4 | 440 | 24.3 | 12.4 | 24.3 | 12.7 |
| name | lora_v1 | 440 | 30.5 | 10.0 | 30.5 | 10.1 |
| name | lora_v2 | 440 | 32.5 | 9.1 | 32.5 | 9.1 |
| number | base_g4 | 844 | 59.8 | 10.4 | 59.8 | 10.7 |
| number | lora_v1 | 844 | 82.5 | 3.2 | 82.5 | 3.2 |
| number | lora_v2 | 844 | 86.7 | 2.6 | 86.7 | 2.6 |
| place | base_g4 | 286 | 67.8 | 8.1 | 66.8 | 9.0 |
| place | lora_v1 | 286 | 74.8 | 6.2 | 73.8 | 6.9 |
| place | lora_v2 | 286 | 72.4 | 5.8 | 71.3 | 6.5 |
| text | base_g4 | 367 | 43.3 | 10.3 | 42.8 | 10.4 |
| text | lora_v1 | 367 | 57.5 | 5.9 | 57.5 | 5.9 |
| text | lora_v2 | 367 | 61.9 | 5.3 | 61.9 | 5.3 |

### Campos curtos (até 3 caracteres, fora dos totais)

| Modelo | Campos | Exatos livre | Exatos local |
|---|---|---|---|
| base_g4 | 1081 | 91.8 | 89.3 |
| lora_v1 | 1081 | 95.5 | 94.9 |
| lora_v2 | 1081 | 96.5 | 96.2 |

## Página

Completude: fração dos campos achados com CER <= 0.2 (livre). Truncada: `fim = length` ou últimos campos ausentes sem bloco na altura deles. Laço: trecho repetido em sequência (>= 100 caracteres, >= 3 vezes) ou saída >= 1.5x a dos outros modelos. Impresso: CER entre a saída do modelo e a da referência (base_g4) depois de apagar os valores manuscritos.

| Modelo | Páginas | Completude | Truncadas | Laços | Impresso CER vs ref | Idem, sem maiúsc./minúsc. | Páginas com impresso alterado |
|---|---|---|---|---|---|---|---|
| base_g4 | 100 | 84.6 | 1.0 | 1.0 | - | - | - |
| lora_v1 | 100 | 92.6 | 0.0 | 0.0 | 26.32 | 26.08 | 100.0 |
| lora_v2 | 100 | 93.5 | 0.0 | 0.0 | 26.50 | 26.26 | 99.0 |

## Comparação pareada com base_g4

Diferença em pontos percentuais (modelo - referência) nas mesmas páginas e campos; IC de 95% por bootstrap pareado sobre páginas; McNemar exato campo a campo (só ref = acertos só da referência, só modelo = acertos só do modelo).

| Modelo | Métrica | Ref | Modelo | Diferença | IC 95% | Só ref / só modelo | McNemar p |
|---|---|---|---|---|---|---|---|
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

## Por template

| template | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| certidao_casamento | base_g4 | 16 | 91 | 48.4 | 48.4 | 25.0 | 92.5 | 0.0 | 0.0 |
| certidao_casamento | lora_v1 | 16 | 91 | 58.2 | 58.2 | 28.1 | 95.0 | 0.0 | 0.0 |
| certidao_casamento | lora_v2 | 16 | 91 | 62.6 | 62.6 | 31.2 | 93.8 | 0.0 | 0.0 |
| certidao_casamento_cnj | base_g4 | 17 | 473 | 49.7 | 49.5 | 25.4 | 81.5 | 0.0 | 0.0 |
| certidao_casamento_cnj | lora_v1 | 17 | 473 | 63.8 | 63.8 | 35.4 | 91.3 | 0.0 | 0.0 |
| certidao_casamento_cnj | lora_v2 | 17 | 473 | 66.8 | 66.8 | 41.5 | 93.4 | 0.0 | 0.0 |
| certidao_nascimento_cnj | base_g4 | 16 | 351 | 50.1 | 49.0 | 23.8 | 86.8 | 0.0 | 0.0 |
| certidao_nascimento_cnj | lora_v1 | 16 | 351 | 59.0 | 58.1 | 28.7 | 89.2 | 0.0 | 0.0 |
| certidao_nascimento_cnj | lora_v2 | 16 | 351 | 61.5 | 60.7 | 30.0 | 92.5 | 0.0 | 0.0 |
| certidao_obito | base_g4 | 16 | 383 | 54.0 | 54.0 | 28.6 | 82.9 | 6.2 | 6.2 |
| certidao_obito | lora_v1 | 16 | 383 | 64.8 | 64.8 | 29.7 | 88.9 | 0.0 | 0.0 |
| certidao_obito | lora_v2 | 16 | 383 | 68.9 | 68.9 | 29.7 | 90.4 | 0.0 | 0.0 |
| dnv | base_g4 | 35 | 1350 | 59.9 | 59.9 | 19.6 | 82.4 | 0.0 | 0.0 |
| dnv | lora_v1 | 35 | 1350 | 77.2 | 77.2 | 27.1 | 95.4 | 0.0 | 0.0 |
| dnv | lora_v2 | 35 | 1350 | 78.7 | 78.7 | 26.2 | 95.4 | 0.0 | 0.0 |

## Por level

| level | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| 1 | base_g4 | 26 | 694 | 56.3 | 56.3 | 23.1 | 88.8 | 0.0 | 0.0 |
| 1 | lora_v1 | 26 | 694 | 69.3 | 69.3 | 31.6 | 94.0 | 0.0 | 0.0 |
| 1 | lora_v2 | 26 | 694 | 70.5 | 70.5 | 29.1 | 94.9 | 0.0 | 0.0 |
| 2 | base_g4 | 33 | 922 | 58.4 | 57.8 | 24.5 | 85.3 | 0.0 | 0.0 |
| 2 | lora_v1 | 33 | 922 | 74.0 | 73.6 | 30.2 | 96.0 | 0.0 | 0.0 |
| 2 | lora_v2 | 33 | 922 | 77.8 | 77.4 | 34.5 | 97.1 | 0.0 | 0.0 |
| 3 | base_g4 | 25 | 705 | 55.3 | 55.3 | 27.4 | 84.3 | 4.0 | 4.0 |
| 3 | lora_v1 | 25 | 705 | 70.2 | 70.2 | 35.0 | 91.0 | 0.0 | 0.0 |
| 3 | lora_v2 | 25 | 705 | 71.2 | 71.2 | 35.9 | 91.2 | 0.0 | 0.0 |
| 4 | base_g4 | 16 | 327 | 46.5 | 46.5 | 20.9 | 76.9 | 0.0 | 0.0 |
| 4 | lora_v1 | 16 | 327 | 59.3 | 59.3 | 20.9 | 85.7 | 0.0 | 0.0 |
| 4 | lora_v2 | 16 | 327 | 63.3 | 63.3 | 28.4 | 87.5 | 0.0 | 0.0 |

## Por split

| split | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| test | base_g4 | 100 | 2648 | 55.6 | 55.4 | 24.3 | 84.6 | 1.0 | 1.0 |
| test | lora_v1 | 100 | 2648 | 69.9 | 69.8 | 30.5 | 92.6 | 0.0 | 0.0 |
| test | lora_v2 | 100 | 2648 | 72.3 | 72.2 | 32.5 | 93.5 | 0.0 | 0.0 |
