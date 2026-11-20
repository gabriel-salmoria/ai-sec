# Avaliação de páginas inteiras: teste_local

94 páginas com gabarito e predição de todos os modelos. 0 campos cuja tinta perdeu os acentos ficam de fora. Campos de até 3 caracteres vão para uma tabela à parte. Valores em %.

Livre: o valor pode estar em qualquer ponto da saída. Local: só nos blocos cuja caixa encosta na do campo. CER = distância de edição / tamanho do campo. Campos numéricos comparados só por letras e dígitos.

## Campos manuscritos

| Modelo | Campos | Exatos livre | CER livre | Exatos local | CER local | Nomes | Nomes exatos livre | Nomes exatos local | Nomes CER local |
|---|---|---|---|---|---|---|---|---|---|
| base | 2491 | 50.0 | 15.1 | 49.8 | 15.7 | 407 | 20.9 | 20.9 | 17.9 |

### Por classe de campo

| Classe | Modelo | Campos | Exatos livre | CER livre | Exatos local | CER local |
|---|---|---|---|---|---|---|
| closed | base | 537 | 68.5 | 9.4 | 68.5 | 10.4 |
| date | base | 126 | 68.3 | 4.3 | 68.3 | 4.5 |
| name | base | 407 | 20.9 | 17.2 | 20.9 | 17.9 |
| number | base | 781 | 55.8 | 15.5 | 55.6 | 16.1 |
| place | base | 262 | 56.5 | 13.7 | 55.3 | 14.9 |
| text | base | 378 | 32.5 | 18.3 | 32.3 | 18.5 |

### Campos curtos (até 3 caracteres, fora dos totais)

| Modelo | Campos | Exatos livre | Exatos local |
|---|---|---|---|
| base | 990 | 90.5 | 88.0 |

## Página

Completude: fração dos campos achados com CER <= 0.2 (livre). Truncada: `fim = length` ou últimos campos ausentes sem bloco na altura deles. Laço: trecho repetido em sequência (>= 100 caracteres, >= 3 vezes) ou saída >= 1.5x a dos outros modelos. Impresso: CER entre a saída do modelo e a da referência (base) depois de apagar os valores manuscritos.

| Modelo | Páginas | Completude | Truncadas | Laços | Impresso CER vs ref | Idem, sem maiúsc./minúsc. | Páginas com impresso alterado |
|---|---|---|---|---|---|---|---|
| base | 94 | 78.0 | 1.1 | 1.1 | - | - | - |

## Por template

| template | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| certidao_casamento | base | 17 | 116 | 36.2 | 35.3 | 20.6 | 86.6 | 0.0 | 0.0 |
| certidao_casamento_cnj | base | 16 | 450 | 44.9 | 44.7 | 22.0 | 74.0 | 0.0 | 0.0 |
| certidao_nascimento_cnj | base | 15 | 337 | 40.7 | 39.5 | 17.3 | 75.2 | 0.0 | 0.0 |
| certidao_obito | base | 14 | 342 | 52.0 | 52.0 | 24.1 | 79.7 | 0.0 | 0.0 |
| dnv | base | 32 | 1246 | 55.1 | 55.1 | 19.8 | 76.0 | 3.1 | 3.1 |

## Por level

| level | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| 1 | base | 21 | 643 | 54.4 | 54.3 | 24.0 | 82.5 | 0.0 | 0.0 |
| 2 | base | 33 | 830 | 53.9 | 53.4 | 23.1 | 80.8 | 0.0 | 0.0 |
| 3 | base | 29 | 778 | 45.4 | 45.2 | 19.7 | 72.1 | 0.0 | 0.0 |
| 4 | base | 11 | 240 | 40.0 | 40.0 | 10.0 | 76.1 | 9.1 | 9.1 |

## Por split

| split | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| test | base | 94 | 2491 | 50.0 | 49.8 | 20.9 | 78.0 | 1.1 | 1.1 |
