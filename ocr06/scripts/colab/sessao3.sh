#!/usr/bin/env bash
# Session 3 (L4): lora_v1 BF16 on the full tests; base on the pages it hasn't read yet;
# FP8/INT4 versions on the half sets. Unattended, resumable, time-capped steps.
# Hard steps stop the session on failure (FAIL); quantization steps are soft (SKIP) so a
# failed INT4 can't throw away the BF16 results.
set -uo pipefail
cd /content/ai-sec/ocr06
export HF_HOME="$PWD/models/hf_cache" TOKENIZERS_PARALLELISM=false
ST=logs/colab_status_s3; mkdir -p logs
log() { echo "$* $(date -u +%T)" >> "$ST"; }
run() {  # run <hard|soft> <name> <minutes> <command...>
    local kind=$1 name=$2 mins=$3; shift 3
    grep -q -E "^(OK|SKIP) $name " "$ST" 2>/dev/null && return 0
    log "START $name"
    if timeout "${mins}m" "$@" > "logs/s3_$name.out" 2>&1; then log "OK $name"; return 0; fi
    if [ "$kind" = hard ]; then log "FAIL $name (veja logs/s3_$name.out)"; exit 1; fi
    log "SKIP $name (falhou; veja logs/s3_$name.out)"; return 1
}
V=.venv-vllm/bin/python; G=.venv-gpu/bin/python; D=.venv/bin/python; CFG=configs/paginas.yaml
INF="$V -m ocr06.model.pages_infer --config $CFG"
CHK="$D scripts/colab/check_preds.py"
HALF="metade_local_aval metade_ocrsd"
run hard gpu_check 2 bash -c 'nvidia-smi; v=$(nvidia-smi | grep -o "CUDA Version: [0-9]*" | grep -o "[0-9]*$"); [ "$v" -ge 13 ]'
run hard setup 40 bash scripts/setup.sh --gpu
run hard sets_check 2 $D -c '
import json, pathlib
for n in ["smoke5","teste_local","teste_ocrsd","bressay100","teste_local_novos","teste_ocrsd_novos","metade_local_aval","metade_ocrsd"]:
    rows=[json.loads(l) for l in open(f"data/pages/{n}/pages.jsonl")]
    miss=[r["id"] for r in rows if not pathlib.Path("data/"+r["image"]).exists()]
    print(n, len(rows), "faltando", len(miss)); assert not miss
assert pathlib.Path("models/lora_v1/adapter/adapter_model.safetensors").exists()'
# 1) the main question: lora_v1 BF16
run hard merge_v1 30 $G -m ocr06.model.merge --config $CFG --skip-fp8
run hard v1_smoke 20 $INF --models ft --sets smoke5 --out-name lora_v1
run hard v1_smoke_check 2 $CHK experiments/paginas/lora_v1/smoke5.jsonl
run hard v1_testes 150 $INF --models ft --sets teste_ocrsd teste_local bressay100 --out-name lora_v1
# 2) base on what it hasn't read (26 new local, 6 new OCRSD, BRESSAY with today's pipeline)
run hard base_novos 60 $INF --models base --sets teste_local_novos teste_ocrsd_novos bressay100 --out-name base
# 3) quantized versions on the half sets (soft)
run soft quant_fp8 30 $G -m ocr06.model.merge --config $CFG --skip-merge && \
    run soft v1_fp8 40 $INF --models ft_fp8 --sets $HALF --out-name lora_v1_fp8
run soft quant_int4 30 $G -m ocr06.model.merge --config $CFG --skip-merge --skip-fp8 --int4 && \
    run soft v1_int4 40 $INF --models ft_int4 --sets $HALF --out-name lora_v1_int4
run soft quant_base 30 $G -m ocr06.model.merge --config $CFG --base-only && \
    run soft base_fp8 40 $INF --models base_fp8_ours --sets $HALF --out-name base_fp8
log DONE
