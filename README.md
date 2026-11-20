# INE5448: IA e Segurança (UFSC)

Trabalhos da disciplina INE5448. O principal é a PoC **OCR-06: OCR Adaptativo com
Aprendizagem Assistida**, que ajusta com LoRA o Chandra OCR 2 para ler campos manuscritos de
certidões de Registro Civil, principalmente nomes raros, sem treinar com dados de pessoas
reais. Tutor: Lucas Mayr.

| Pasta | Conteúdo |
|---|---|
| [`ocr06/`](ocr06/) | código da PoC: dados, geradores, treino, quantização e avaliação (ver o [README](ocr06/README.md)) |
| [`POC/`](POC/) | relatório da PoC em LaTeX; versões entregues em `POC/v0` a `POC/v5`, sendo a final [`POC/v5/INE5448_RelFinal_Salmoria_Gabriel.pdf`](POC/v5/INE5448_RelFinal_Salmoria_Gabriel.pdf) |
| [`proposta/`](proposta/) | proposta inicial da PoC |
| [`apresentacao/`](apresentacao/) | apresentação intermediária (13/10/2026) |
| [`apresentacao_final/`](apresentacao_final/) | apresentação curta de resultados (17/11/2026) |
| [`apresentacao_workshop/`](apresentacao_workshop/) | apresentação no Workshop LabREC (novembro de 2026) |
| [`t1/`](t1/) | Trabalho 1: formulário público com envio por e-mail no n8n |
| [`t2/`](t2/) | Trabalho 2: análise crítica de artigo |

Os documentos em LaTeX compilam com `latexmk -lualatex main.tex` (relatório) ou
`latexmk -pdf main.tex` (apresentações), dentro de cada pasta.

## Resultado principal da PoC

Em 200 certidões sintéticas de teste, a fração de campos manuscritos lidos sem erro passou de
55% (Chandra OCR 2 original) para 72% (lora_v2), e a de nomes de 24% para 33% no teste com
nomes nunca vistos e de 40% para 50% no teste com nomes na frequência real. Quantizado em
INT4, o modelo ocupa 5 GiB. Detalhes, limitações e reprodução em [`ocr06/README.md`](ocr06/README.md)
e no relatório final.
