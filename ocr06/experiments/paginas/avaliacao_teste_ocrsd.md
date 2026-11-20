# Avaliação de páginas inteiras: teste_ocrsd

94 páginas com gabarito e predição de todos os modelos. 204 campos cuja tinta perdeu os acentos ficam de fora. Campos de até 3 caracteres vão para uma tabela à parte. Valores em %.

Livre: o valor pode estar em qualquer ponto da saída. Local: só nos blocos cuja caixa encosta na do campo. CER = distância de edição / tamanho do campo. Campos numéricos comparados só por letras e dígitos.

## Campos manuscritos

| Modelo | Campos | Exatos livre | CER livre | Exatos local | CER local | Nomes | Nomes exatos livre | Nomes exatos local | Nomes CER local |
|---|---|---|---|---|---|---|---|---|---|
| base | 1460 | 84.6 | 1.7 | 84.6 | 1.8 | 399 | 84.7 | 84.7 | 1.4 |

### Por classe de campo

| Classe | Modelo | Campos | Exatos livre | CER livre | Exatos local | CER local |
|---|---|---|---|---|---|---|
| closed | base | 244 | 74.6 | 6.1 | 74.6 | 7.0 |
| date | base | 94 | 98.9 | 0.1 | 98.9 | 0.1 |
| name | base | 399 | 84.7 | 1.3 | 84.7 | 1.4 |
| number | base | 305 | 95.4 | 0.5 | 95.4 | 0.5 |
| place | base | 132 | 93.2 | 1.5 | 93.2 | 1.7 |
| text | base | 286 | 72.7 | 1.3 | 72.7 | 1.3 |

### Campos curtos (até 3 caracteres, fora dos totais)

| Modelo | Campos | Exatos livre | Exatos local |
|---|---|---|---|
| base | 475 | 97.1 | 96.2 |

## Página

Completude: fração dos campos achados com CER <= 0.2 (livre). Truncada: `fim = length` ou últimos campos ausentes sem bloco na altura deles. Laço: trecho repetido em sequência (>= 100 caracteres, >= 3 vezes) ou saída >= 1.5x a dos outros modelos. Impresso: CER entre a saída do modelo e a da referência (base) depois de apagar os valores manuscritos.

| Modelo | Páginas | Completude | Truncadas | Laços | Impresso CER vs ref | Idem, sem maiúsc./minúsc. | Páginas com impresso alterado |
|---|---|---|---|---|---|---|---|
| base | 94 | 96.1 | 0.0 | 0.0 | - | - | - |

## Por template

| template | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| certidao_casamento | base | 37 | 141 | 86.5 | 86.5 | 81.4 | 97.2 | 0.0 | 0.0 |
| certidao_casamento_cnj | base | 27 | 836 | 86.7 | 86.7 | 87.3 | 98.3 | 0.0 | 0.0 |
| certidao_nascimento_cnj | base | 10 | 102 | 82.4 | 82.4 | 83.8 | 96.2 | 0.0 | 0.0 |
| certidao_obito | base | 20 | 381 | 79.8 | 79.8 | 81.6 | 90.9 | 0.0 | 0.0 |

## Por writing

| writing | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| aaron1259 | base | 19 | 116 | 76.7 | 76.7 | 83.0 | 92.9 | 0.0 | 0.0 |
| font | base | 47 | 1208 | 86.0 | 86.0 | 86.6 | 98.1 | 0.0 | 0.0 |
| sjvasquez | base | 20 | 120 | 80.0 | 80.0 | 82.0 | 98.0 | 0.0 | 0.0 |
| wpvnteam | base | 8 | 16 | 68.8 | 68.8 | 58.3 | 87.5 | 0.0 | 0.0 |

## Por split

| split | Modelo | Páginas | Campos | Exatos livre | Exatos local | Nomes exatos local | Completude | Truncadas | Laços |
|---|---|---|---|---|---|---|---|---|---|
| test | base | 94 | 1460 | 84.6 | 84.6 | 84.7 | 96.1 | 0.0 | 0.0 |
