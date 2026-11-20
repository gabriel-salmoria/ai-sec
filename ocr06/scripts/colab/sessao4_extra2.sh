#!/usr/bin/env bash
# After the extras: lora_v1 on the normal set (merge lora_v1 here, same config as session 3).
set -uo pipefail
cd /content/ai-sec/ocr06
exec 9>/content/s4y.lock; flock -n 9 || { echo "extra2 já está rodando"; exit 0; }
export HF_HOME="$PWD/models/hf_cache" TOKENIZERS_PARALLELISM=false
ST=logs/colab_status_s4y
log() { echo "$* $(date -u +%T)" >> "$ST"; }
run() {
    local name=$1 mins=$2; shift 2
    grep -q -E "^(OK|SKIP) $name " "$ST" 2>/dev/null && return 0
    log "START $name"
    if timeout "${mins}m" "$@" > "logs/s4y_$name.out" 2>&1; then log "OK $name"; return 0; fi
    log "SKIP $name (falhou; veja logs/s4y_$name.out)"; return 1
}
run merge_v1 10 .venv-gpu/bin/python -m ocr06.model.merge --config configs/paginas.yaml --skip-fp8 && \
    run v1_normal 20 .venv-vllm/bin/python -m ocr06.model.pages_infer --config configs/paginas.yaml --models ft --sets forms_v2_normal --out-name lora_v1
log DONE
