# OCR-06: dados, treino e avaliação

Código da PoC (INE5448). A parte de dados coleta estatísticas públicas de nomes, gera
linhas manuscritas sintéticas, prepara o BRESSAY e monta os conjuntos no formato de
conversa do VLM; roda em CPU. A parte de modelo faz o baseline do Chandra, o
fine-tuning LoRA, a versão FP8 e a avaliação; roda no servidor com GPU.

## Uso no servidor

```bash
git clone git@github.com:gabriel-salmoria/ai-sec.git && cd ai-sec/ocr06
scripts/setup.sh        # ambientes de dados, treino e vLLM (detecta a GPU sozinho)
scripts/run.sh          # dados -> baseline -> treino -> FP8 -> avaliação
```

Pra não prender o terminal: `nohup scripts/run.sh > /dev/null 2>&1 &` e `tail -f logs/run_*.log`.
Antes do treino longo, vale um `scripts/run.sh teste-rapido` (minutos): inferência em 32
linhas + 100 passos de treino, mede velocidade e memória.

| Comando | O que faz |
|---|---|
| `scripts/run.sh dados` | lexicon → fonts → bressay → generate → mix → exp1 (CPU, ~1 h) |
| `scripts/run.sh modelo` | baseline → treino → quantizar → avaliacao (GPU) |
| `scripts/run.sh <etapa>` | etapa avulsa (lista no cabeçalho de `scripts/run.sh`) |

Variáveis: `WORKERS=16`, `NAME=v1` (dataset), `LIMIT=100` (inferência parcial),
`HF_HOME` (cache dos modelos, padrão `models/hf_cache`), `CONFIG=configs/outra.yaml`.
No laptop, sem GPU: `scripts/setup.sh --sem-gpu` e `scripts/run.sh dados`.

### Ambientes
| Pasta | Pra quê | Principais pacotes |
|---|---|---|
| `.venv` | dados e métricas | augraphy, opencv, numpy |
| `.venv-gpu` | treino, fusão, FP8 | torch, transformers, peft, llmcompressor |
| `.venv-vllm` | inferência | vllm |

São separados porque o vLLM fixa versões de torch/transformers diferentes das do treino.
As versões instaladas ficam em `logs/versoes-*.txt`.

### Modelo
- **Base:** `datalab-to/chandra-ocr-2`, um fine-tune do Qwen3.5-4B. O treino LoRA parte da
  versão BF16; o encoder de visão fica congelado.
- **Baseline:** Chandra BF16 e o FP8 de terceiros (`dangvansam/chandra-ocr-2-FP8-dynamic`),
  cada um com o nosso prompt e com o prompt nativo (que responde em HTML).
- **Depois do treino:** o LoRA é fundido ao modelo (`models/<run>/merged`) e quantizado
  em FP8 com a mesma receita do FP8 de terceiros (`models/<run>/merged-fp8`).
- **Avaliação** (`experiments/modelos/comparacao.{md,tex}`): CER/WER da linha e CER dos
  nomes por tipo, por grupo (comum/raro) e em nomes inéditos no treino.

## Decisões de dados

- **Prioridade pela população.** Prenomes, sobrenomes e municípios entram em ordem de
  frequência real. O corte (`vocab.coverage: auto`) é a maior lista em que cada nome
  aparece pelo menos `min_expected` vezes no treino. Com 40 mil imagens ficam ~10 mil
  prenomes (94% da população), ~19 mil sobrenomes (95%) e ~3,8 mil municípios (97%).
- **Temperatura.** Dentro do vocabulário, o sorteio usa q ∝ p^α (α = 0,5).
- **Teste com nomes inéditos.** Os nomes comuns aparecem em todos os splits. 10% dos
  raros do vocabulário ficam só no teste e 5% só na validação. A mistura de comuns e
  raros é a mesma em todos os splits.
- **BRESSAY.** Usa a partição oficial por autor. Linhas com trecho ilegível ou riscado
  são descartadas. Os nomes nas redações são marcados por heurística, para revisão em
  `data/bressay/nomes_para_revisao.csv`.
- **Mistura.** O treino é majoritariamente sintético (BRESSAY ≤ 45%, como pede a POC).
  No teste, cada nome indica se foi visto no treino (`visto_no_treino`).
- **Privacidade.** TSE e RFB têm nomes completos de pessoas reais. Eles são lidos em
  streaming e só ficam contagens por palavra. Os .zip são apagados e sobrenomes com
  menos de 5 ocorrências são descartados.

## Formato final (`data/final/<NAME>/*.jsonl`)

```json
{"id": "...", "source": "sintetico|bressay", "image": "synthetic/v0/train/images/train_0000000.jpg",
 "text": "Maria da Silva", "entities": [{"type": "prenome", "key": "MARIA", "bucket": "comum", ...}],
 "messages": [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": "Transcreva..."}]},
              {"role": "assistant", "content": [{"type": "text", "text": "Maria da Silva"}]}]}
```
Os caminhos de imagem são relativos a `ocr06/data/`.

## Fontes de dados

| Dado | Fonte |
|---|---|
| Prenomes e frequência (Censo 2010) | IBGE, via espelho Brasil.IO; o top-20 é conferido com a API do IBGE |
| Sobrenomes, partículas, grafias com acento | TSE: candidatos de 2020 e 2024 |
| Sobrenomes | Receita Federal: sócios pessoa física |
| Municípios e população | IBGE: localidades e Censo 2022 (SIDRA 4709) |
| Linhas manuscritas reais | BRESSAY (Zenodo 11637681, CC-BY 4.0) |
| Fontes manuscritas | Google Fonts (OFL/Apache) |

## Estrutura

```
ocr06/
  configs/default.yaml   todos os parâmetros
  scripts/               setup.sh, run.sh
  src/ocr06/
    sources.py           download e agregação (IBGE, TSE, RFB)
    lexicon.py           filtros, acentos, comum/raro, nomes inventados (opcionais)
    vocab.py             seleção por frequência + nomes reservados para val/teste
    sampler.py           sorteio estratificado e montagem das linhas
    fonts.py render.py degrade.py generate.py   imagens sintéticas
    bressay.py           BRESSAY: download, limpeza, marcação de nomes
    mix.py               conjuntos finais no formato do VLM
    experiment1.py       Experimento 1
    evaluate.py          CER/WER, por grupo de nome (Python puro)
    model/               infer.py (vLLM), train.py (LoRA), merge.py (fusão + FP8)
  data/                  gerado (fora do git)
  experiments/exp1/      resultados do Experimento 1
  models/                adaptador, modelos fundidos e cache do HF (fora do git)
  logs/                  logs do run.sh/setup.sh
```
