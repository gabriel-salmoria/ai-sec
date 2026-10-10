#!/usr/bin/env bash
# Roda o OCR-06. Sem argumentos roda tudo (dados + modelo).
#
#   scripts/run.sh                     tudo
#   scripts/run.sh dados               lexicon fonts bressay generate mix exp1
#   scripts/run.sh modelo              baseline treino quantizar avaliacao
#   scripts/run.sh teste-rapido        checa a parte de GPU em minutos (32 linhas + 100 passos)
#   scripts/run.sh <etapa> [...]       etapas avulsas, na ordem dada
#
# Etapas de dados (CPU):  lexicon fonts bressay generate mix exp1
# Etapas de modelo (GPU): baseline  piloto  treino  quantizar  avaliacao  metricas
#   baseline   Chandra BF16 e FP8, sem treino, com o nosso prompt e o nativo (vLLM)
#   piloto     100 passos de treino só para medir velocidade e memória
#   treino     LoRA completo (com validação e parada antecipada)
#   quantizar  funde o LoRA e gera a versão FP8
#   avaliacao  modelo treinado (BF16 e FP8) nos dois testes + tabela comparativa
#   metricas   só recalcula as métricas/tabela a partir das predições existentes
#
# Variáveis: CONFIG=configs/default.yaml  WORKERS=auto  NAME=v0 (dataset)
#            LIMIT=N (inferência só nas N primeiras linhas)  HF_HOME (cache dos modelos)
# Logs em logs/. No servidor, sem prender o terminal:
#   nohup scripts/run.sh > /dev/null 2>&1 &     e acompanhe com   tail -f logs/run_*.log
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/_comum.sh

CONFIG="${CONFIG:-configs/default.yaml}"
export HF_HOME="${HF_HOME:-$PWD/models/hf_cache}"
export TOKENIZERS_PARALLELISM=false
mkdir -p logs models

DATA_STEPS=(lexicon fonts bressay generate mix exp1)
MODEL_STEPS=(baseline treino quantizar avaliacao)

STEPS=()
[ $# -eq 0 ] && set -- tudo
for a in "$@"; do
    case "$a" in
        tudo) STEPS+=("${DATA_STEPS[@]}" "${MODEL_STEPS[@]}") ;;
        dados) STEPS+=("${DATA_STEPS[@]}") ;;
        modelo) STEPS+=("${MODEL_STEPS[@]}") ;;
        teste-rapido) STEPS+=(teste-rapido) ;;
        lexicon|fonts|bressay|generate|mix|exp1|baseline|piloto|treino|quantizar|avaliacao|metricas)
            STEPS+=("$a") ;;
        *) erro "etapa desconhecida: $a (veja o cabeçalho de scripts/run.sh)"; exit 2 ;;
    esac
done

precisa() {  # precisa <venv>
    if [ ! -x "$1/bin/python" ]; then
        erro "$1 não existe; rode scripts/setup.sh$([ "$1" != .venv ] && echo ' --gpu')"
        exit 1
    fi
}

dados()  { precisa .venv; .venv/bin/python -m ocr06 --config "$CONFIG" ${WORKERS:+--workers "$WORKERS"} "$@"; }
infer()  { precisa .venv-vllm; .venv-vllm/bin/python -m ocr06.model.infer --config "$CONFIG" ${LIMIT:+--limit "$LIMIT"} "$@"; }
treinar(){ precisa .venv-gpu; .venv-gpu/bin/python -m ocr06.model.train --config "$CONFIG" "$@"; }
fundir() { precisa .venv-gpu; .venv-gpu/bin/python -m ocr06.model.merge --config "$CONFIG" "$@"; }
metricas(){ precisa .venv; .venv/bin/python -m ocr06.evaluate --config "$CONFIG"; }

etapa() {
    local s="$1"
    titulo "$s  ($(date +%H:%M:%S))"
    case "$s" in
        lexicon|fonts|bressay|exp1) dados "$s" ;;
        generate|mix) dados "$s" ${NAME:+--name "$NAME"} ;;
        baseline)
            # Um processo por modelo: o vLLM só libera a GPU quando o processo termina.
            infer --models base --prompts nosso chandra
            infer --models base_fp8 --prompts nosso chandra
            metricas ;;
        piloto) treinar --pilot ;;
        treino) treinar ;;
        quantizar) fundir ;;
        avaliacao)
            infer --models ft
            infer --models ft_fp8
            metricas ;;
        metricas) metricas ;;
        teste-rapido)
            LIMIT=32 infer --models base_fp8 --prompts nosso chandra
            metricas
            treinar --pilot ;;
    esac
}

LOG="logs/run_$(date +%Y%m%d_%H%M%S).log"
{
    echo "início: $(date)  host: $(uname -n)  etapas: ${STEPS[*]}"
    command -v nvidia-smi >/dev/null && nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader || true
    for s in "${STEPS[@]}"; do etapa "$s"; done
    titulo "fim: $(date)"
    [ -f experiments/modelos/comparacao.md ] && echo "  tabela comparativa: experiments/modelos/comparacao.md" || true
} 2>&1 | tee "$LOG"
