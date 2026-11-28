# INE5448: IA e Segurança (UFSC)

Trabalhos da disciplina INE5448. O principal é a PoC **OCR-06: OCR Adaptativo com Aprendizagem Assistida**, que ajusta com LoRA o Chandra OCR 2 para ler campos manuscritos de certidões de Registro Civil, principalmente nomes raros, sem treinar com dados de pessoas reais. Tutor: Lucas Mayr.

Para conhecer o trabalho, a ordem sugerida é a apresentação do workshop ([`apresentacoes/2026-11-23_workshop/INE5448_Apresentacao_Salmoria_Gabriel.pdf`](apresentacoes/2026-11-23_workshop/INE5448_Apresentacao_Salmoria_Gabriel.pdf)), depois o relatório final ([`POC/`](POC/)) e, para reproduzir, o [README do código](ocr06/README.md). A origem de cada número do relatório está em [`ocr06/experiments/README.md`](ocr06/experiments/README.md).

| Pasta | Conteúdo |
|---|---|
| [`POC/`](POC/) | relatório da PoC, com as fontes do relatório final no template da disciplina em `POC/salmoria-gabriel/` e cada versão entregue em `POC/vN/` (ver o [README](POC/README.md)) |
| [`apresentacoes/`](apresentacoes/) | apresentação intermediária (13/10/2026), de resultados (17/11/2026) e no IV Workshop Acadêmico do Registro Civil (23/11/2026) |
| [`ocr06/`](ocr06/) | código da PoC: dados, geradores, treino, quantização e avaliação, com os resultados em `ocr06/experiments/` |
| [`proposta/`](proposta/) | proposta inicial da PoC |
| [`t1/`](t1/) | Trabalho 1: formulário público com envio por e-mail no n8n |
| [`t2/`](t2/) | Trabalho 2: análise crítica de artigo |

Os documentos em LaTeX compilam com `latexmk -pdf main.tex` dentro de cada pasta.

## Resultado principal da PoC

Em 200 certidões sintéticas de teste, a fração de campos manuscritos lidos sem erro passou de 55% (Chandra OCR 2 original) para 72% (lora_v2), e a de nomes de 24% para 33% no teste com nomes nunca vistos e de 40% para 50% no teste com nomes na frequência real. O ganho só apareceu quando o treino passou de linhas para páginas inteiras. Quantizado em INT4, o modelo ocupa 5 GiB. A principal limitação é a perda de generalidade, porque em redações do BRESSAY e formulários do XFUND-PT o modelo original continua melhor.
