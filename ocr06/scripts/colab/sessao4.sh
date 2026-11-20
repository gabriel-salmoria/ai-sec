#!/usr/bin/env bash
# Session 4 (G4 or A100): continue lora_v1 on 1,700 new pages (lora_v2), then test on the same GPU:
# hard batch (teste_local, 100) with base + lora_v2 BF16/FP8/INT4, normal batch
# (forms_v2_normal, 100) with base + lora_v2 BF16, and base FP8 only if the PC driver opens
# its gate (balance check). Unattended, resumable, time-capped; one copy at a time.
set -uo pipefail
cd /content/ai-sec/ocr06
exec 9>/content/s4.lock; flock -n 9 || { echo "sessao4 já está rodando"; exit 0; }
export HF_HOME="$PWD/models/hf_cache" TOKENIZERS_PARALLELISM=false
ST=logs/colab_status_s4; mkdir -p logs
log() { echo "$* $(date -u +%T)" >> "$ST"; }
run() {  # run <hard|soft> <name> <minutes> <command...>
    local kind=$1 name=$2 mins=$3; shift 3
    grep -q -E "^(OK|SKIP) $name " "$ST" 2>/dev/null && return 0
    log "START $name"
    if timeout "${mins}m" "$@" > "logs/s4_$name.out" 2>&1; then log "OK $name"; return 0; fi
    if [ "$kind" = hard ]; then log "FAIL $name (veja logs/s4_$name.out)"; exit 1; fi
    log "SKIP $name (falhou; veja logs/s4_$name.out)"; return 1
}
gate() {  # waits for data/.gate_<name> (go) or data/.parar (skip) from the PC, max 6 min (then skip)
    grep -q "^OK gate_$1 " "$ST" 2>/dev/null && return 0
    log "START gate_$1"
    for _ in $(seq 36); do
        [ -f "data/.gate_$1" ] && { log "OK gate_$1"; return 0; }
        [ -f data/.parar ] && break
        sleep 10
    done
    log "STOP gate_$1"; return 1
}
G=.venv-gpu/bin/python; V=.venv-vllm/bin/python; D=.venv/bin/python; CFG=configs/paginas_v2.yaml
INF="$V -m ocr06.model.pages_infer --config $CFG"
HARD=teste_local; NORMAL=forms_v2_normal
run hard gpu_check 2 bash -c 'nvidia-smi; v=$(nvidia-smi | grep -o "CUDA Version: [0-9]*" | grep -o "[0-9]*$"); [ "$v" -ge 13 ]'
run hard setup 40 bash scripts/setup.sh --gpu
run hard wait_data 40 bash -c 'until [ -f data/.upload_ok ]; do sleep 10; done'
run hard torch_check 5 $G -c 'import torch; assert torch.cuda.is_available(); print(torch.__version__, torch.cuda.get_device_name(0))'
run hard data_check 3 $G -c '
import json, pathlib
for f in ("final/pages_v2/train", "final/pages_v2/val", "pages/teste_local/pages", "pages/forms_v2_normal/pages", "pages/smoke5/pages"):
    rows=[json.loads(l) for l in open(f"data/{f}.jsonl")]
    miss=[r["id"] for r in rows if not pathlib.Path("data/"+r["image"]).exists()]
    print(f, len(rows), "faltando", len(miss)); assert not miss and rows
assert pathlib.Path("models/lora_v1/adapter/adapter_model.safetensors").exists()'
# Uso da GPU a cada 30 s (o keep-alive mostra a última linha)
pgrep -f "nvidia-smi --query-gpu" >/dev/null || (nvidia-smi --query-gpu=timestamp,utilization.gpu,memory.used,memory.total \
    --format=csv,noheader -l 30 > logs/gpu_s4.csv 2>&1 &)
# 1 época sobre as 1.700 páginas (107 passos de 16 páginas). Páginas por passo conforme a
# memória da placa (96/80 GB: 4; 40 GB: 2), com acumulação para manter 16 por passo; se
# faltar memória mesmo assim, tenta com 1 página por passo. Mesma conta de treino.
MEM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1)
if [ "$MEM" -ge 70000 ]; then TCFG=$CFG; else TCFG=configs/paginas_v2_b2.yaml; fi
echo "memória ${MEM} MiB -> treino com $TCFG" >> logs/s4_lote.txt
treina() { $G -m ocr06.model.train --config "$1" $( ls -d models/lora_v2/checkpoints/checkpoint-* >/dev/null 2>&1 && echo --resume ); }
if ! grep -q "^OK train " "$ST" 2>/dev/null; then
    log "START train ($TCFG)"
    if timeout 200m bash -c "$(declare -f treina); G=$G; treina $TCFG" > logs/s4_train.out 2>&1; then log "OK train"
    elif grep -q "OutOfMemoryError\|CUDA out of memory" logs/s4_train.out && [ "$TCFG" != configs/paginas_v2_b1.yaml ]; then
        log "OOM com $TCFG; tentando 1 página por passo"; mv logs/s4_train.out logs/s4_train_oom.out
        rm -rf models/lora_v2/checkpoints
        if timeout 200m bash -c "$(declare -f treina); G=$G; treina configs/paginas_v2_b1.yaml" > logs/s4_train.out 2>&1; then log "OK train"
        else log "FAIL train (veja logs/s4_train.out)"; exit 1; fi
    else log "FAIL train (veja logs/s4_train.out)"; exit 1; fi
fi
run hard merge 20 $G -m ocr06.model.merge --config $CFG --skip-fp8
run hard v2_smoke 15 $INF --models ft --sets smoke5 --out-name lora_v2
run hard v2_smoke_check 2 $D scripts/colab/check_preds.py experiments/paginas/lora_v2/smoke5.jsonl
run hard v2_hard 45 $INF --models ft --sets $HARD --out-name lora_v2
run hard base_hard 45 $INF --models base --sets $HARD --out-name base_g4
if run soft quant 40 $G -m ocr06.model.merge --config $CFG --skip-merge --int4; then
    run soft fp8_hard 45 $INF --models ft_fp8 --sets $HARD --out-name lora_v2_fp8
    run soft int4_hard 45 $INF --models ft_int4 --sets $HARD --out-name lora_v2_int4
fi
run soft v2_normal 45 $INF --models ft --sets $NORMAL --out-name lora_v2
run soft base_normal 45 $INF --models base --sets $NORMAL --out-name base_g4
if gate basefp8; then
    run soft quant_base 30 $G -m ocr06.model.merge --config $CFG --base-only && \
        run soft basefp8_hard 45 $INF --models base_fp8_ours --sets $HARD --out-name base_fp8
fi
log DONE
