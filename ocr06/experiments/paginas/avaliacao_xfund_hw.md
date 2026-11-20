# Avaliação de páginas inteiras: xfund_hw

50 páginas com gabarito e predição de todos os modelos. 0 campos cuja tinta perdeu os acentos ficam de fora. Campos de até 3 caracteres vão para uma tabela à parte. Valores em %.

Livre: o valor pode estar em qualquer ponto da saída. Local: só nos blocos cuja caixa encosta na do campo. CER = distância de edição / tamanho do campo. Campos numéricos comparados só por letras e dígitos.

## Campos manuscritos

| Modelo | Campos | Exatos livre | CER livre | Exatos local | CER local | Nomes | Nomes exatos livre | Nomes exatos local | Nomes CER local |
|---|---|---|---|---|---|---|---|---|---|
| base | 1446 | 53.0 | 6.6 | 7.7 | 75.3 | 0 | - | - | - |
| ft | 1446 | 52.3 | 8.6 | 8.4 | 76.7 | 0 | - | - | - |
| lora_v2 | 1446 | 43.8 | 8.8 | 5.1 | 79.2 | 0 | - | - | - |

### Por classe de campo

| Classe | Modelo | Campos | Exatos livre | CER livre | Exatos local | CER local |
|---|---|---|---|---|---|---|
| text | base | 1446 | 53.0 | 6.6 | 7.7 | 75.3 |
| text | ft | 1446 | 52.3 | 8.6 | 8.4 | 76.7 |
| text | lora_v2 | 1446 | 43.8 | 8.8 | 5.1 | 79.2 |

### Campos curtos (até 3 caracteres, fora dos totais)

| Modelo | Campos | Exatos livre | Exatos local |
|---|---|---|---|
| base | 390 | 93.1 | 9.5 |
| ft | 390 | 89.7 | 10.0 |
| lora_v2 | 390 | 86.9 | 8.2 |

## Página

Completude: fração dos campos achados com CER <= 0.2 (livre). Truncada: `fim = length` ou últimos campos ausentes sem bloco na altura deles. Laço: trecho repetido em sequência (>= 100 caracteres, >= 3 vezes) ou saída >= 1.5x a dos outros modelos. Impresso: CER entre a saída do modelo e a da referência (base) depois de apagar os valores manuscritos.

| Modelo | Páginas | Completude | Truncadas | Laços | Impresso CER vs ref | Idem, sem maiúsc./minúsc. | Páginas com impresso alterado |
|---|---|---|---|---|---|---|---|
| base | 50 | 88.5 | 4.0 | 0.0 | - | - | - |
| ft | 50 | 86.8 | 2.0 | 0.0 | 6.89 | 6.76 | 100.0 |
| lora_v2 | 50 | 84.2 | 8.0 | 6.0 | 20.03 | 19.70 | 100.0 |

## Comparação pareada com base

Diferença em pontos percentuais (modelo - referência) nas mesmas páginas e campos; IC de 95% por bootstrap pareado sobre páginas; McNemar exato campo a campo (só ref = acertos só da referência, só modelo = acertos só do modelo).

| Modelo | Métrica | Ref | Modelo | Diferença | IC 95% | Só ref / só modelo | McNemar p |
|---|---|---|---|---|---|---|---|
| ft | campos/exato_livre | 53.0 | 52.3 | -0.7 | [-3.3, +2.1] | 59 / 49 | 0.387 |
| ft | campos/exato_local | 7.7 | 8.4 | +0.6 | [-1.3, +2.9] | 20 / 29 | 0.253 |
| ft | completude | 88.5 | 86.8 | -1.7 | [-4.2, +0.3] | - | - |
| lora_v2 | campos/exato_livre | 53.0 | 43.8 | -9.2 | [-12.1, -6.2] | 175 / 42 | 1.71e-20 |
| lora_v2 | campos/exato_local | 7.7 | 5.1 | -2.6 | [-5.5, -0.1] | 54 / 16 | 5.85e-06 |
| lora_v2 | completude | 88.5 | 84.2 | -4.3 | [-7.5, -0.8] | - | - |
