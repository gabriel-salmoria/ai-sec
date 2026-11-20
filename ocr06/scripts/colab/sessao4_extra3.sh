#!/usr/bin/env bash
# After lora_v1's run: lora_v2 BF16 on real documents (BRESSAY pt-BR essays, XFUND-PT forms).
set -uo pipefail
cd /content/ai-sec/ocr06
exec 9>/content/s4z.lock; flock -n 9 || { echo "extra3 já está rodando"; exit 0; }
export HF_HOME="$PWD/models/hf_cache" TOKENIZERS_PARALLELISM=false
ST=logs/colab_status_s4z
log() { echo "$* $(date -u +%T)" >> "$ST"; }
log "START v2_real"
if timeout 25m .venv-vllm/bin/python -m ocr06.model.pages_infer --config configs/paginas_v2.yaml --models ft \
        --sets xfund_hw bressay --out-name lora_v2 > logs/s4z_v2_real.out 2>&1; then log "OK v2_real"
else log "SKIP v2_real (falhou; veja logs/s4z_v2_real.out)"; fi
log DONE
