#!/usr/bin/env bash
# Extras after session 4 (DONE), on the same machine and models: lora_v2 FP8/INT4 on the normal
# set, and a one-page-at-a-time speed run (3 hard pages) for base, lora_v2 BF16/FP8/INT4.
# Separate status file; every step is soft (a failure only skips that step).
set -uo pipefail
cd /content/ai-sec/ocr06
exec 9>/content/s4x.lock; flock -n 9 || { echo "extra já está rodando"; exit 0; }
export HF_HOME="$PWD/models/hf_cache" TOKENIZERS_PARALLELISM=false
ST=logs/colab_status_s4x
log() { echo "$* $(date -u +%T)" >> "$ST"; }
run() {  # run <name> <minutes> <command...>
    local name=$1 mins=$2; shift 2
    grep -q -E "^(OK|SKIP) $name " "$ST" 2>/dev/null && return 0
    log "START $name"
    if timeout "${mins}m" "$@" > "logs/s4x_$name.out" 2>&1; then log "OK $name"; else log "SKIP $name (falhou; veja logs/s4x_$name.out)"; fi
}
V=.venv-vllm/bin/python
INF="$V -m ocr06.model.pages_infer --config configs/paginas_v2.yaml"
INF1="$V -m ocr06.model.pages_infer --config configs/paginas_v2_lote1.yaml --sets teste_local --limit 3"
run fp8_normal 20 $INF --models ft_fp8 --sets forms_v2_normal --out-name lora_v2_fp8
run int4_normal 20 $INF --models ft_int4 --sets forms_v2_normal --out-name lora_v2_int4
run lote1_base 10 $INF1 --models base --out-name lote1_base
run lote1_bf16 10 $INF1 --models ft --out-name lote1_lora_v2
run lote1_fp8 10 $INF1 --models ft_fp8 --out-name lote1_lora_v2_fp8
run lote1_int4 10 $INF1 --models ft_int4 --out-name lote1_lora_v2_int4
log DONE
