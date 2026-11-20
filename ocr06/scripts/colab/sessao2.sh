#!/usr/bin/env bash
# Session 2 (G4): train lora_v1 on pages. Unattended, resumable, time-capped steps.
#   BUDGET_H = hours of training allowed (the pilot measures speed and sets max_steps).
set -uo pipefail
cd /content/ai-sec/ocr06
export HF_HOME="$PWD/models/hf_cache" TOKENIZERS_PARALLELISM=false
BUDGET_H="${BUDGET_H:-2.0}"
ST=logs/colab_status_s2; mkdir -p logs
log() { echo "$* $(date -u +%T)" >> "$ST"; }
step() {
    local name=$1 mins=$2; shift 2
    grep -q "^OK $name " "$ST" 2>/dev/null && return 0
    log "START $name"
    if timeout "${mins}m" "$@" > "logs/s2_$name.out" 2>&1; then log "OK $name"
    else log "FAIL $name (veja logs/s2_$name.out)"; exit 1; fi
}
G=.venv-gpu/bin/python; CFG=configs/paginas.yaml
step gpu_check 2 bash -c 'nvidia-smi; v=$(nvidia-smi | grep -o "CUDA Version: [0-9]*" | grep -o "[0-9]*$"); [ "$v" -ge 13 ]'
step setup 40 bash scripts/setup.sh --gpu
step wait_data 30 bash -c 'until [ -f data/.upload_ok ]; do sleep 10; done'
step torch_check 5 $G -c 'import torch; assert torch.cuda.is_available(); print(torch.__version__, torch.cuda.get_device_name(0))'
step data_check 3 $G -c '
import json, pathlib
for s in ("train", "val"):
    rows=[json.loads(l) for l in open(f"data/final/pages_v1/{s}.jsonl")]
    miss=[r["id"] for r in rows if not pathlib.Path("data/"+r["image"]).exists()]
    print(s, len(rows), "faltando", len(miss)); assert not miss'
step pilot 30 $G -m ocr06.model.train --config $CFG --pilot
step budget 2 $G -c "
import json, math
p=json.load(open('models/lora_v1/piloto.json')); sps=p['amostras_por_segundo']
n=sum(1 for _ in open('data/final/pages_v1/train.jsonl')); eff=16
full=math.ceil(n/eff); cap=int($BUDGET_H*3600*sps/eff)
steps=min(full, cap); open('models/lora_v1/max_steps','w').write(str(steps))
print(f'{sps:.3f} amostras/s; época = {full} passos; orçamento = {cap}; usando {steps} ({steps*eff/n:.0%} das páginas); pico {p.get(\"memoria_pico_gb\")} GB')"
step train 300 bash -c "$G -m ocr06.model.train --config $CFG --max-steps \$(cat models/lora_v1/max_steps) \$( ls -d models/lora_v1/checkpoints/checkpoint-* >/dev/null 2>&1 && echo --resume )"
log DONE
