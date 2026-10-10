#!/usr/bin/env bash
# Prepara tudo para rodar o OCR-06 (dados + modelo). Um comando só:
#
#   scripts/setup.sh              # dados; e GPU (treino + vLLM) se houver nvidia-smi
#   scripts/setup.sh --gpu        # força a instalação da parte de GPU
#   scripts/setup.sh --sem-gpu    # só a parte de dados (ex.: no laptop)
#
# Ambientes criados (cada um isolado, pois vLLM, treino e dados pedem versões
# diferentes de torch/transformers):
#   .venv       dados: coleta, geração sintética, BRESSAY, avaliação
#   .venv-gpu   treino LoRA, fusão e quantização FP8 (torch, transformers, peft, llmcompressor)
#   .venv-vllm  inferência (vLLM)
# Opções: PYTHON=/caminho/python3.x   LOCK=1 (versões exatas testadas do ambiente de dados)
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/_comum.sh

GPU=auto
for a in "$@"; do
    case "$a" in
        --gpu) GPU=1 ;;
        --sem-gpu) GPU=0 ;;
        *) erro "opção desconhecida: $a"; exit 2 ;;
    esac
done
if [ "$GPU" = auto ]; then
    if command -v nvidia-smi >/dev/null && nvidia-smi >/dev/null 2>&1; then GPU=1; else GPU=0; fi
fi

PY="${PYTHON:-python3}"
titulo "Python"
if ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
    erro "Python >= 3.10 necessário (atual: $("$PY" --version 2>&1)). Use PYTHON=/caminho/python3.x"
    exit 1
fi
ok "$("$PY" --version)"
mkdir -p logs

novo_venv() {  # novo_venv <pasta>
    [ -d "$1" ] || "$PY" -m venv "$1"
    "$1/bin/python" -m pip install --quiet --upgrade pip
}

titulo "Ambiente de dados (.venv)"
novo_venv .venv
if [ "${LOCK:-0}" = 1 ]; then .venv/bin/pip install --quiet -r requirements.lock.txt; fi
.venv/bin/pip install --quiet -e .
if ! .venv/bin/python -c "import cv2" 2>/dev/null; then
    aviso "OpenCV não carregou (provável falta de libGL): trocando por opencv-python-headless"
    v=$(.venv/bin/python -m pip show opencv-python | awk '/^Version/{print $2}')
    .venv/bin/pip uninstall --quiet -y opencv-python
    .venv/bin/pip install --quiet "opencv-python-headless==${v}"
fi
.venv/bin/python -c "import ocr06, augraphy, cv2" && ok "ocr06, augraphy e OpenCV ok"

if [ "$GPU" = 1 ]; then
    nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader | sed 's/^/  GPU: /'

    titulo "Ambiente de treino (.venv-gpu)"
    novo_venv .venv-gpu
    .venv-gpu/bin/pip install --quiet -r requirements-gpu.txt
    .venv-gpu/bin/pip install --quiet --no-deps -e .
    .venv-gpu/bin/python - <<'PY'
import torch, transformers, peft
assert torch.cuda.is_available(), "torch não enxerga a GPU (CUDA)"
print(f"  torch {torch.__version__} (CUDA {torch.version.cuda}) | transformers {transformers.__version__} | peft {peft.__version__}")
PY
    ok "treino ok"
    .venv-gpu/bin/pip freeze > logs/versoes-gpu.txt

    titulo "Ambiente de inferência (.venv-vllm)"
    novo_venv .venv-vllm
    .venv-vllm/bin/pip install --quiet -r requirements-vllm.txt
    .venv-vllm/bin/pip install --quiet --no-deps -e .
    .venv-vllm/bin/python -c "import vllm; print('  vllm', vllm.__version__)"
    ok "vLLM ok"
    .venv-vllm/bin/pip freeze > logs/versoes-vllm.txt

    titulo "Compatibilidade com o Chandra (só baixa a config, ~10 KB)"
    for env in .venv-gpu .venv-vllm; do
        if $env/bin/python -c "
from transformers import AutoConfig
c = AutoConfig.from_pretrained('datalab-to/chandra-ocr-2')
print('  $env: transformers reconhece', c.model_type)" 2>/dev/null; then :; else
            aviso "$env: o transformers instalado não reconhece o Chandra (qwen3_5); atualize-o"
        fi
    done
else
    aviso "sem GPU: instalei só a parte de dados (use --gpu para forçar)"
fi

titulo "Pronto"
echo "  Próximo passo:  scripts/run.sh            (dados + modelo)"
echo "                  scripts/run.sh dados      (só a parte de dados)"
