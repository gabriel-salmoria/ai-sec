#!/usr/bin/env bash
# Drives session 2 from the PC: opens the G4, uploads the code and starts the install at
# once, uploads the data in parallel, keeps the kernel busy, copies logs + adapter +
# latest checkpoint home every 10 min, and stops the VM on DONE or FAIL.
#   scripts/colab/rodar_s2.sh /tmp/ocr06_s2 [BUDGET_H]
set -uo pipefail
cd "$(dirname "$0")/../.."               # ocr06/
P="$1"; BUDGET_H="${2:-2.0}"; export SESSION=s2
C=scripts/colab/cssh
pull() { $C 'cd /content/ai-sec/ocr06 && ck=$(ls -d models/lora_v1/checkpoints/checkpoint-* 2>/dev/null | sort -V | tail -1);
         tar -czf - logs models/lora_v1/adapter models/lora_v1/*.json $ck 2>/dev/null' < /dev/null | tar -xzf - -C . ; }
colab usage | tail -3
colab new -s "$SESSION" --gpu G4 || { echo "não abriu a G4"; exit 1; }
$C 'mkdir -p /content/ai-sec && tar -xzf - -C /content/ai-sec' < "${P}_code.tar.gz" || { colab stop -s "$SESSION"; exit 1; }
# start detached (stdin closed, so ssh returns at once)
cat > /tmp/start_s2.py <<PY
import subprocess
subprocess.Popen("BUDGET_H=$BUDGET_H bash scripts/colab/sessao2.sh > /content/s2.out 2>&1", shell=True,
                 start_new_session=True, stdin=subprocess.DEVNULL, cwd="/content/ai-sec/ocr06")
print("sessao2 iniciada")
PY
colab exec -s "$SESSION" -f /tmp/start_s2.py
$C 'tar -xzf - -C /content/ai-sec && touch /content/ai-sec/ocr06/data/.upload_ok' < "${P}_data.tar.gz" || echo "upload de dados falhou"
( while sleep 600; do pull; done ) & PULLER=$!
seen=""
while true; do
    colab exec -s "$SESSION" -f scripts/colab/keepalive_s2.py > logs/s2_keepalive_last.out 2>&1
    st=$($C 'cat /content/ai-sec/ocr06/logs/colab_status_s2 2>/dev/null' < /dev/null || true)
    [ "$st" != "$seen" ] && { pull; seen="$st"; echo "$st" | tail -2; }
    if echo "$st" | grep -q -E "DONE|FAIL"; then break; fi
    echo "keep-alive caiu às $(date +%T); reconectando"; sleep 10
done
kill $PULLER 2>/dev/null; pull
colab stop -s "$SESSION"
colab usage | tail -3
echo "$st"
