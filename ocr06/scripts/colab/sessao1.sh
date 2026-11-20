#!/usr/bin/env bash
# Session 1 (L4): base Chandra on the blank forms and the form tests; lora_v0 on half.
# Runs unattended and is resumable: finished steps (OK in the status file) are skipped.
# Each step has a time cap so a hang can't keep the GPU billing.
set -uo pipefail
cd /content/ai-sec/ocr06
export HF_HOME="$PWD/models/hf_cache" TOKENIZERS_PARALLELISM=false
ST=logs/colab_status_s1; mkdir -p logs
log() { echo "$* $(date -u +%T)" >> "$ST"; }
step() {  # step <name> <minutes> <command...>
    local name=$1 mins=$2; shift 2
    grep -q "^OK $name " "$ST" 2>/dev/null && return 0
    log "START $name"
    if timeout "${mins}m" "$@" > "logs/s1_$name.out" 2>&1; then log "OK $name"
    else log "FAIL $name (veja logs/s1_$name.out)"; exit 1; fi
}
V=.venv-vllm/bin/python; G=.venv-gpu/bin/python
# As rodas de torch/vLLM fixadas são cu130: driver com CUDA 12.x não serve (falha já aqui,
# antes de 15 min de instalação).
step gpu_check 2 bash -c 'nvidia-smi; python3 --version; df -h /content | tail -1; free -g;
    v=$(nvidia-smi | grep -o "CUDA Version: [0-9]*" | grep -o "[0-9]*$"); echo "CUDA major $v"; [ "$v" -ge 13 ]'
step setup 40 bash scripts/setup.sh --gpu
step torch_check 5 $G -c 'import torch; assert torch.cuda.is_available(); print(torch.__version__, torch.cuda.get_device_name(0)); x=torch.randn(512,512,device="cuda",dtype=torch.bfloat16); print((x@x).float().abs().mean())'
step sets_check 2 .venv/bin/python -c '
import json, pathlib
for n in ["modelos_em_branco","smoke5","teste_local","teste_ocrsd","metade_local","metade_ocrsd"]:
    rows=[json.loads(l) for l in open(f"data/pages/{n}/pages.jsonl")]
    miss=[r["id"] for r in rows if not pathlib.Path("data/"+r["image"]).exists()]
    print(n, len(rows), "faltando", len(miss)); assert not miss'
step base_smoke 30 $V -m ocr06.model.pages_infer --models base --sets smoke5 modelos_em_branco --out-name base
step base_smoke_check 2 .venv/bin/python scripts/colab/check_preds.py experiments/paginas/base/smoke5.jsonl
step base_formas 120 $V -m ocr06.model.pages_infer --models base --sets teste_local teste_ocrsd --out-name base
step merge_v0 30 $G -m ocr06.model.merge --skip-fp8
step v0_smoke 30 $V -m ocr06.model.pages_infer --models ft --sets smoke5 --out-name lora_v0
step v0_smoke_check 2 .venv/bin/python scripts/colab/check_preds.py experiments/paginas/lora_v0/smoke5.jsonl  # vazio = merge quebrado
step v0_metade 90 $V -m ocr06.model.pages_infer --models ft --sets metade_local metade_ocrsd --out-name lora_v0
log DONE
