# Nomes vistos e inéditos nas páginas de teste

Palavras vistas: as que aparecem em algum campo de 3500 páginas de treino (30013 palavras). Acerto exato local dos campos de nome, em %.

## teste_local

| Grupo | Campos | base_g4 | lora_v1 | lora_v2 | lora_v2_fp8 | lora_v2_int4 |
|---|---|---|---|---|---|---|
| todas as palavras vistas | 17 | 35.3 | 64.7 | 58.8 | 58.8 | 58.8 |
| alguma palavra inédita | 423 | 23.9 | 29.1 | 31.4 | 29.6 | 27.7 |

## forms_v2_normal

| Grupo | Campos | base_g4 | lora_v2 |
|---|---|---|---|
| todas as palavras vistas | 367 | 44.7 | 51.8 |
| alguma palavra inédita | 121 | 27.3 | 45.5 |
