# OCR-06: OCR adaptativo para nomes manuscritos em certidões

Código da PoC OCR-06 (INE5448, UFSC). O Chandra OCR 2, um OCR de pesos abertos derivado do
Qwen3.5-4B, é ajustado com LoRA para ler os campos manuscritos de certidões de Registro Civil,
principalmente nomes raros, sem que dados de pessoas reais entrem no treino. Os nomes vêm de
contagens agregadas do IBGE, do TSE e da Receita Federal, e as certidões de treino são
sintéticas.

O trabalho teve duas etapas:

1. **Linhas** (`lora_v0`): linhas manuscritas sintéticas com nomes brasileiros e linhas reais
   do BRESSAY. Melhorou muito a leitura de linhas, mas não a de certidões inteiras.
2. **Páginas** (`lora_v1`, `lora_v2`): certidões inteiras do OCRSD e de um gerador próprio, no
   formato HTML que o Chandra já devolve. `lora_v2` também foi quantizado em FP8 e INT4.

O relatório final está em [`../POC/v6/INE5448_RelFinal_Salmoria_Gabriel.pdf`](../POC/v6/INE5448_RelFinal_Salmoria_Gabriel.pdf).

## Resultados principais

Linhas (5.146 linhas do BRESSAY de autores fora do treino; 4.000 linhas sintéticas com fontes
e nomes fora do treino):

| | Chandra | lora_v0 |
|---|---|---|
| CER no BRESSAY | 20,1% | 4,9% |
| CER no sintético | 8,6% | 3,4% |
| Nomes inéditos lidos sem erro | 70,9% | 79,7% |

Páginas (acerto exato dos campos manuscritos; IC 95% por bootstrap pareado):

| Teste | Chandra | lora_v1 | lora_v2 | lora_v2 FP8 | lora_v2 INT4 |
|---|---|---|---|---|---|
| Difícil (100 págs., nomes nunca vistos): campos | 55,4% | 69,8% | 72,2% | 71,7% | 69,9% |
| Difícil: nomes | 24,3% | 30,5% | 32,5% | 30,7% | 28,9% |
| Normal (100 págs., nomes pela frequência real): campos | 55,8% | 69,2% | 72,0% | 71,9% | 71,6% |
| Normal: nomes | 40,4% | 44,5% | 50,2% | 49,6% | 49,4% |
| OCRSD (94 págs., escritores fora do treino): campos | 84,6% | 95,5% | – | – | – |

Na RTX PRO 6000, os pesos ocupam 8,6 GiB em BF16, 6,2 GiB em FP8 e 5,0 GiB em INT4, e uma
página sozinha leva 22,6 s, 17,7 s e 14,9 s. Fora das certidões (redações do BRESSAY,
formulários do XFUND-PT) o `lora_v2` fica abaixo do Chandra original. Os relatórios completos
estão em `experiments/paginas/` (ver [Resultados](#resultados)).

## Estrutura

```
ocr06/
  configs/
    default.yaml            etapa de linhas: dados, treino, inferência e avaliação
    paginas.yaml            etapa de páginas: treino do lora_v1
    paginas_v2.yaml         etapa de páginas: treino do lora_v2 (continua o lora_v1)
    paginas_v2_b1.yaml, paginas_v2_b2.yaml   o mesmo treino com lotes de 1 ou 2 páginas (GPUs menores)
    paginas_v2_lote1.yaml   igual ao v2, uma página por vez (medida de velocidade)
    prompt_chandra_layout.txt  prompt nativo do Chandra
  scripts/
    setup.sh run.sh         ambientes e etapas de linhas
    ocrsd/                  cliente da API do OCRSD, fila de lotes e extração das páginas
    hw/                     renderizadores dos escritores neurais (VATr++ e Graves)
    colab/                  scripts usados para rodar as sessões de GPU no Google Colab
    erros_paginas.py        leitura de cada modelo, campo a campo
    memorizacao_paginas.py  acerto em nomes vistos e inéditos
    figs_apresentacao_final.py  figuras do relatório e das apresentações
  src/ocr06/
    sources.py lexicon.py   coleta e agregação dos nomes (IBGE, TSE, Receita)
    vocab.py sampler.py     vocabulário por frequência, partição e sorteio
    fonts.py render.py degrade.py generate.py   linhas sintéticas
    bressay.py mix.py       BRESSAY e conjuntos de linhas
    preprocess.py guard.py  normalização das linhas e controles de saída
    evaluate.py             CER/WER por grupo de nome (linhas)
    experiment1.py experiment2.py   Experimentos 1 e 2 (sem modelo)
    forms/                  gerador local de certidões e gabaritos de página
    pages_eval.py           avaliação de campos em página inteira
    pages_real.py pages.py  BRESSAY e XFUND-PT em página inteira
    model/                  train.py (LoRA), merge.py (fusão, FP8, INT4),
                            infer.py (linhas) e pages_infer.py (páginas), com vLLM
  tests/                    testes do avaliador de páginas e do treino em página
  experiments/              resultados (predições, métricas, relatórios)
  data/lexicon/             léxico agregado (no git); o resto de data/ é gerado
  models/ third_party/ logs/   fora do git
```

## Ambientes

| Pasta | Para quê | Principais pacotes |
|---|---|---|
| `.venv` | dados, geração e métricas (CPU) | augraphy, opencv, numpy |
| `.venv-gpu` | treino, fusão e quantização | torch, transformers 5.21, peft 0.21, llmcompressor 0.15 (`requirements-gpu.txt`) |
| `.venv-vllm` | inferência | vllm (`requirements-vllm.txt`) |
| `.venv-hw-vatrpp` | escritor neural VATr++ (GPU de preferência) | torch 2.8, transformers 4.46 |
| `.venv-hw-graves` | escritor neural Graves (CPU) | numpy, pillow; tensorflow 2.12 só para converter o checkpoint |
| `.venv-cputest` | testes em CPU | torch (CPU), transformers, peft, pytest |

Os três primeiros são criados por `scripts/setup.sh` (com `--sem-gpu` no laptop). São
separados porque o vLLM fixa versões de torch e transformers diferentes das do treino.

Hardware usado: dados e geração num PC comum (CPU; GTX 1060 para o VATr++); treino e
inferência numa RTX PRO 6000 de 96 GB (pico de 60,7 GB no treino em página). O Chandra em
BF16 também roda numa L4 de 24 GB.

```bash
git clone https://github.com/gabriel-salmoria/ai-sec.git && cd ai-sec/ocr06
scripts/setup.sh                       # detecta a GPU; no laptop: scripts/setup.sh --sem-gpu
.venv-cputest/bin/python -m pytest tests -q   # 21 testes, CPU, sem os pesos do Chandra
```

## Etapa 1: linhas

```bash
scripts/run.sh dados     # lexicon → fonts → bressay → generate → mix → exp1 (CPU, ~1 h)
scripts/run.sh modelo    # baseline → treino → quantizar → avaliacao (GPU)
scripts/run.sh <etapa>   # etapa avulsa (lista no cabeçalho de scripts/run.sh)
```

Variáveis: `WORKERS=16`, `NAME=v1` (conjunto), `LIMIT=100` (inferência parcial), `HF_HOME`
(cache dos modelos, padrão `models/hf_cache`), `CONFIG=configs/outra.yaml`. Antes do treino
longo, `scripts/run.sh teste-rapido` mede velocidade e memória em poucos minutos.

O léxico (`data/lexicon/`) está no git porque as APIs do IBGE, do TSE e da Receita recusam
conexões de fora do Brasil; numa máquina no exterior, pule a etapa `lexicon`.

Decisões de dados:

- **Frequência real.** Prenomes, sobrenomes e municípios entram por ordem de frequência na
  população, até a maior lista em que cada um aparece pelo menos 2 vezes no treino. Com 40
  mil imagens ficam cerca de 10 mil prenomes (94% da população), 19 mil sobrenomes (95%) e
  3,8 mil municípios (97%). O sorteio usa q ∝ p^α, com α = 0,5.
- **Nomes inéditos.** Os nomes comuns (80% da população) aparecem em todos os conjuntos; 10%
  dos raros ficam só no teste e 5% só na validação. A mesma partição vale para as certidões.
- **BRESSAY.** Partição oficial por autor; linhas com trecho ilegível ou riscado saem.
- **Mistura.** O treino é majoritariamente sintético (o script para se o BRESSAY passar de 45%).

## Etapa 2: páginas

### Dados

**OCRSD.** O gerador de certidões sintéticas de Tiago Siqueira, PoC da mesma disciplina hospedada em <https://ocrsd.onrcpn.org.br>, exige
uma credencial de acesso, lida de `~/.config/ocrsd/workspace` (ou do arquivo em
`OCRSD_WORKSPACE_FILE`) e nunca gravada no repositório. As páginas geradas não estão no git.

```bash
.venv/bin/python scripts/ocrsd/gen.py scripts/ocrsd/jobs_wave4b.json   # fila de lotes; retoma de onde parou
.venv/bin/python scripts/ocrsd/extract.py                               # data/pages/ocrsd/pages.jsonl
```

`extract.py` mantém os cinco documentos usados (casamento antigo e CNJ, nascimento CNJ, óbito
e DNV), guarda em cada campo o valor desenhado e o pedido e marca `accent_stripped` nos campos
em que o escritor neural perdeu acentos (esses ficam fora da perda e da avaliação).

**Escritores neurais.** Ficam em `third_party/` (fora do git):

- VATr++: `git clone https://huggingface.co/blowing-up-groundhogs/vatrpp third_party/vatrpp`
  (MIT); renderizador em `scripts/hw/render_vatrpp.py`.
- Graves: o checkpoint `model-17900` de <https://github.com/sjvasquez/handwriting-synthesis>,
  em `third_party/sjvasquez/`, convertido uma vez para
  `third_party/graves_np/model-17900.npz` com `scripts/hw/graves_np.py` (precisa de
  TensorFlow só nessa conversão); a inferência é um port em NumPy, em CPU.

Os dois só escrevem textos sem acento, ç ou º; nas páginas escritas por eles, os campos
acentuados ficam em branco. As comparações em `experiments/hw_bakeoff/report.md`.

**Gerador local.**

```bash
.venv/bin/python -m ocr06.forms.assets                 # modelos em branco e mapas de campos (só leitura na API)
.venv/bin/python -m ocr06.forms.build --name forms_v2 --count 1600 \
    --hands font:0.3,vatrpp:0.5,graves:0.2            # data/pages/forms_v2/
```

Cada página usa um registro do OCRSD com prenomes, sobrenomes e municípios trocados por nomes
do léxico (respeitando a partição e bloqueando os nomes do teste do BRESSAY), uma mão e uma
caneta, e um nível de dificuldade de 1 a 4. `forms/sheet.py` monta folhas de amostra.

**Gabaritos.** O texto impresso de cada modelo vem do próprio Chandra lendo o modelo em
branco; os valores manuscritos entram como blocos sobre os campos. Peso na perda: impresso
0,3, manuscrito 1, campos sem acento 0; nomes 2 no `lora_v2`.

```bash
.venv/bin/python -m ocr06.forms.targets from-blank                 # printed.json por modelo
.venv/bin/python -m ocr06.forms.targets build3 --out data/final/pages_v2
```

### Treino, fusão e quantização

```bash
.venv-gpu/bin/python -m ocr06.model.train --config configs/paginas_v2.yaml --pilot   # mede velocidade
.venv-gpu/bin/python -m ocr06.model.train --config configs/paginas_v2.yaml
.venv-gpu/bin/python -m ocr06.model.merge --config configs/paginas_v2.yaml --int4    # merged, merged-fp8, merged-int4
.venv-gpu/bin/python -m ocr06.model.merge --config configs/paginas_v2.yaml --base-only   # Chandra em FP8, mesma receita
```

LoRA de posto 16 (α = 32) em todas as camadas lineares do modelo de linguagem, encoder de
visão congelado; lotes efetivos de 16 páginas, taxa 1e-4 constante depois do warmup, uma
época, currículo do nível 1 ao 4. `paginas.yaml` parte do Chandra (`lora_v1`);
`paginas_v2.yaml` continua o `lora_v1` (`init_adapter`) com `name_boost: 2.0`, que aumenta o
peso dos tokens de nome quando o modelo os erra. As duas quantizações (FP8 dinâmico e W4A16)
não usam dados de calibração. Os modelos ficam em `models/<run>/` (fora do git).

### Inferência e avaliação

```bash
.venv-vllm/bin/python -m ocr06.model.pages_infer --config configs/paginas_v2.yaml \
    --models base ft ft_fp8 ft_int4 --sets teste_local forms_v2_normal
.venv/bin/python -m ocr06.pages_eval --config configs/paginas_v2.yaml --set teste_local --ref base_g4
.venv/bin/python -m ocr06.pages_real score          # BRESSAY em página (CER/WER)
.venv/bin/python -m ocr06.pages score               # XFUND-PT com campos reescritos à mão
.venv/bin/python scripts/erros_paginas.py --set teste_local --models base_g4 lora_v2
.venv/bin/python scripts/memorizacao_paginas.py
```

Tags de modelo: `base` (Chandra), `base_fp8` (FP8 de terceiros), `base_fp8_ours` (FP8 com a
nossa receita), `ft`, `ft_fp8`, `ft_int4` (o run da configuração). `--out-name` escolhe a pasta
de saída em `experiments/paginas/`.

`pages_eval.py` procura cada campo do gabarito nos blocos da saída cuja caixa encosta na do
campo (acerto exato *local*), separa por classe (nome, data, número, opção fixa, lugar, texto),
mede completude, truncamento e laço, e compara cada modelo com a referência nas mesmas
páginas (IC 95% por bootstrap pareado sobre páginas e McNemar).

`scripts/colab/` tem os scripts que rodaram as sessões no Google Colab (empacotar, enviar,
rodar sem supervisão, copiar os resultados de volta). `NOTES.md` tem as notas da primeira
sessão.

## Resultados

| Arquivo em `experiments/` | Conteúdo |
|---|---|
| `exp1/`, `exp2_integracao/` | Experimentos 1 e 2 (dados e integração, sem modelo) |
| `modelos/comparacao.md` | Experimento 3: linhas, Chandra × lora_v0, BF16 × FP8 |
| `paginas/avaliacao_teste_local.md` | teste difícil, todos os modelos contra o Chandra |
| `paginas/avaliacao_forms_v2_normal.md` | teste normal |
| `paginas/avaliacao_*_v2_vs_v1.md` | lora_v2 contra lora_v1 |
| `paginas/avaliacao_*_quant_vs_v2.md` | FP8 e INT4 contra o lora_v2 em BF16 |
| `paginas/avaliacao_teste_ocrsd_94.md` | teste do OCRSD (lora_v1) |
| `paginas/avaliacao_metade_*.md` | adaptador de linhas (lora_v0) aplicado a certidões |
| `paginas/comparacao_real.md`, `paginas/avaliacao_xfund_hw.md` | BRESSAY e XFUND-PT em página |
| `paginas/erros_*.md`, `paginas/memorizacao_nomes.md` | leituras por campo e nomes vistos × inéditos |
| `paginas/<modelo>/<conjunto>.jsonl` | predições brutas; `*.tempo.json`, tempos de inferência |

## Dados, licenças e privacidade

| Dado | Origem | Uso |
|---|---|---|
| Prenomes (Censo 2010) | IBGE, via Brasil.IO | contagens no léxico |
| Sobrenomes | TSE (candidatos 2020 e 2024), Receita (sócios pessoa física) | só contagens por palavra; arquivos originais apagados |
| Municípios e população | IBGE (Censo 2022) | léxico |
| Linhas e páginas manuscritas reais | BRESSAY (Zenodo 11637681, CC BY 4.0) | treino de linhas e teste |
| Formulários reais | XFUND-PT (CC BY-NC-SA 4.0) | só teste |
| Cadernos manuscritos | PorTEXTO (CC BY-NC 4.0) | só teste |
| Certidões sintéticas | OCRSD (Tiago Siqueira), com credencial | treino e teste; não redistribuídas |
| Fontes manuscritas | Google Fonts (OFL/Apache) | linhas e certidões |
| Escritores neurais | VATr++ (MIT), handwriting-synthesis (sjvasquez) | certidões |

Nenhum nome completo de pessoa real é gravado: TSE e Receita são lidos em streaming e só
ficam contagens por palavra, com sobrenomes de menos de 5 ocorrências descartados. Os nomes
das linhas e certidões sintéticas são sorteados palavra por palavra, então nenhum registro
corresponde a uma pessoa. Nenhuma certidão real foi usada.
