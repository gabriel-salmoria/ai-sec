# Avaliação de páginas inteiras: teste_ocrsd_94

94 páginas com gabarito e predição de todos os modelos. 204 campos cuja tinta perdeu os acentos ficam de fora. Campos de até 3 caracteres vão para uma tabela à parte. Valores em %.

Livre: o valor pode estar em qualquer ponto da saída. Local: só nos blocos cuja caixa encosta na do campo. CER = distância de edição / tamanho do campo. Campos numéricos comparados só por letras e dígitos.

## Campos manuscritos

| Modelo | Campos | Exatos livre | CER livre | Exatos local | CER local | Nomes | Nomes exatos livre | Nomes exatos local | Nomes CER local |
|---|---|---|---|---|---|---|---|---|---|
| base | 1460 | 84.6 | 1.7 | 84.6 | 1.8 | 399 | 84.7 | 84.7 | 1.4 |
| lora_v1 | 1460 | 95.8 | 0.3 | 95.5 | 0.4 | 399 | 95.7 | 95.5 | 0.3 |

### Por classe de campo

| Classe | Modelo | Campos | Exatos livre | CER livre | Exatos local | CER local |
|---|---|---|---|---|---|---|
| closed | base | 244 | 74.6 | 6.1 | 74.6 | 7.0 |
| closed | lora_v1 | 244 | 98.8 | 0.7 | 98.8 | 0.7 |
| date | base | 94 | 98.9 | 0.1 | 98.9 | 0.1 |
| date | lora_v1 | 94 | 98.9 | 0.3 | 98.9 | 0.7 |
| name | base | 399 | 84.7 | 1.3 | 84.7 | 1.4 |
| name | lora_v1 | 399 | 95.7 | 0.3 | 95.5 | 0.3 |
| number | base | 305 | 95.4 | 0.5 | 95.4 | 0.5 |
| number | lora_v1 | 305 | 95.7 | 0.5 | 94.4 | 0.9 |
| place | base | 132 | 93.2 | 1.5 | 93.2 | 1.7 |
| place | lora_v1 | 132 | 98.5 | 0.2 | 98.5 | 0.2 |
| text | base | 286 | 72.7 | 1.3 | 72.7 | 1.3 |
| text | lora_v1 | 286 | 91.3 | 0.3 | 91.3 | 0.3 |

### Campos curtos (até 3 caracteres, fora dos totais)

| Modelo | Campos | Exatos livre | Exatos local |
|---|---|---|---|
| base | 475 | 97.1 | 96.2 |
| lora_v1 | 475 | 99.8 | 97.5 |

## Página

Completude: fração dos campos achados com CER <= 0.2 (livre). Truncada: `fim = length` ou últimos campos ausentes sem bloco na altura deles. Laço: trecho repetido em sequência (>= 100 caracteres, >= 3 vezes) ou saída >= 1.5x a dos outros modelos. Impresso: CER entre a saída do modelo e a da referência (base) depois de apagar os valores manuscritos.

| Modelo | Páginas | Completude | Truncadas | Laços | Impresso CER vs ref | Idem, sem maiúsc./minúsc. | Páginas com impresso alterado |
|---|---|---|---|---|---|---|---|
| base | 94 | 96.1 | 0.0 | 1.1 | - | - | - |
| lora_v1 | 94 | 99.5 | 0.0 | 0.0 | 10.39 | 10.39 | 70.2 |

## Comparação pareada com base

Diferença em pontos percentuais (modelo - referência) nas mesmas páginas e campos; IC de 95% por bootstrap pareado sobre páginas; McNemar exato campo a campo (só ref = acertos só da referência, só modelo = acertos só do modelo).

| Modelo | Métrica | Ref | Modelo | Diferença | IC 95% | Só ref / só modelo | McNemar p |
|---|---|---|---|---|---|---|---|
| lora_v1 | campos/exato_livre | 84.6 | 95.8 | +11.2 | [+8.5, +14.1] | 9 / 173 | 1.7e-40 |
| lora_v1 | campos/exato_local | 84.6 | 95.5 | +10.9 | [+8.1, +14.0] | 13 / 172 | 1.37e-36 |
| lora_v1 | nomes/exato_livre | 84.7 | 95.7 | +11.0 | [+7.0, +16.0] | 2 / 46 | 8.36e-12 |
| lora_v1 | nomes/exato_local | 84.7 | 95.5 | +10.8 | [+6.6, +15.8] | 2 / 45 | 1.6e-11 |
| lora_v1 | completude | 96.1 | 99.5 | +3.5 | [+1.2, +6.5] | - | - |

## Por template

| template | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| certidao_casamento | base | 37 | 141 | 86.5 | 86.5 | 81.4 | 97.2 | 0.0 | 0.0 |
| certidao_casamento | lora_v1 | 37 | 141 | 95.0 | 94.3 | 91.5 | 100.0 | 0.0 | 0.0 |
| certidao_casamento_cnj | base | 27 | 836 | 86.7 | 86.7 | 87.3 | 98.3 | 0.0 | 0.0 |
| certidao_casamento_cnj | lora_v1 | 27 | 836 | 95.9 | 95.5 | 97.6 | 99.4 | 0.0 | 0.0 |
| certidao_nascimento_cnj | base | 10 | 102 | 82.4 | 82.4 | 83.8 | 96.2 | 0.0 | 0.0 |
| certidao_nascimento_cnj | lora_v1 | 10 | 102 | 93.1 | 93.1 | 86.5 | 98.9 | 0.0 | 0.0 |
| certidao_obito | base | 20 | 381 | 79.8 | 79.8 | 81.6 | 90.9 | 0.0 | 5.0 |
| certidao_obito | lora_v1 | 20 | 381 | 96.6 | 96.6 | 96.9 | 99.3 | 0.0 | 0.0 |

## Por writing

| writing | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| aaron1259 | base | 19 | 116 | 76.7 | 76.7 | 83.0 | 92.9 | 0.0 | 5.3 |
| aaron1259 | lora_v1 | 19 | 116 | 96.6 | 96.6 | 96.2 | 99.4 | 0.0 | 0.0 |
| font | base | 47 | 1208 | 86.0 | 86.0 | 86.6 | 98.1 | 0.0 | 0.0 |
| font | lora_v1 | 47 | 1208 | 96.1 | 95.8 | 97.2 | 99.6 | 0.0 | 0.0 |
| sjvasquez | base | 20 | 120 | 80.0 | 80.0 | 82.0 | 98.0 | 0.0 | 0.0 |
| sjvasquez | lora_v1 | 20 | 120 | 92.5 | 91.7 | 86.0 | 99.4 | 0.0 | 0.0 |
| wpvnteam | base | 8 | 16 | 68.8 | 68.8 | 58.3 | 87.5 | 0.0 | 0.0 |
| wpvnteam | lora_v1 | 8 | 16 | 93.8 | 93.8 | 91.7 | 100.0 | 0.0 | 0.0 |

## Por split

| split | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| test | base | 94 | 1460 | 84.6 | 84.6 | 84.7 | 96.1 | 0.0 | 1.1 |
| test | lora_v1 | 94 | 1460 | 95.8 | 95.5 | 95.5 | 99.5 | 0.0 | 0.0 |
