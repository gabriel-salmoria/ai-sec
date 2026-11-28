# Consistência entre campos como sinal de revisão

Campos de nome aos quais cada regra se aplica, erros de leitura e quantos seriam marcados. A linha gabarito aplica a regra aos valores certos: o que ela marca são alarmes que nem um leitor perfeito evitaria.

## teste_local

| Regra | Leitura | Campos | Errados | Errados marcados | Certos marcados |
|---|---|---|---|---|---|
| sexo | base_g4 | 32 | 21 | 2 | 0 |
| sexo | lora_v2 | 32 | 20 | 1 | 1 |
| sexo | gabarito | 32 | 0 | 0 | 1 |
| filiacao | base_g4 | 98 | 67 | 12 | 1 |
| filiacao | lora_v2 | 98 | 60 | 5 | 1 |
| filiacao | gabarito | 98 | 0 | 0 | 2 |

## forms_v2_normal

| Regra | Leitura | Campos | Errados | Errados marcados | Certos marcados |
|---|---|---|---|---|---|
| sexo | base_g4 | 38 | 20 | 4 | 2 |
| sexo | lora_v2 | 38 | 15 | 7 | 3 |
| sexo | gabarito | 38 | 0 | 0 | 5 |
| filiacao | base_g4 | 116 | 61 | 17 | 2 |
| filiacao | lora_v2 | 116 | 41 | 9 | 1 |
| filiacao | gabarito | 116 | 0 | 0 | 1 |
