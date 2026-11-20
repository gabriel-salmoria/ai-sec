#!/usr/bin/env bash
# Drives session 3 from the PC: opens the L4, uploads the pack, starts sessao3.sh through
# the kernel (returns at once), keeps the kernel busy, copies results home every 10 min and
# after each step, and stops the VM on DONE or FAIL.
#   scripts/colab/rodar_s3.sh /path/ocr06_s3.tar.gz
set -uo pipefail
cd "$(dirname "$0")/../.."               # ocr06/
P="$1"; export SESSION=s3
C=scripts/colab/cssh
pull() { $C 'cd /content/ai-sec/ocr06 && tar -czf - logs experiments/paginas 2>/dev/null' < /dev/null | tar -xzf - -C . ; }
colab usage | tail -3
colab new -s "$SESSION" --gpu L4 || { echo "não abriu a L4"; exit 1; }
$C 'mkdir -p /content/ai-sec && tar -xzf - -C /content/ai-sec' < "$P" || { colab stop -s "$SESSION"; exit 1; }
cat > /tmp/start_s3.py <<PY
import subprocess
subprocess.Popen("bash scripts/colab/sessao3.sh > /content/s3.out 2>&1", shell=True,
                 start_new_session=True, stdin=subprocess.DEVNULL, cwd="/content/ai-sec/ocr06")
print("sessao3 iniciada")
PY
colab exec -s "$SESSION" -f /tmp/start_s3.py
( while sleep 600; do pull; done ) & PULLER=$!
seen=""
while true; do
    colab exec -s "$SESSION" -f scripts/colab/keepalive_s3.py > logs/s3_keepalive_last.out 2>&1
    st=$($C 'cat /content/ai-sec/ocr06/logs/colab_status_s3 2>/dev/null' < /dev/null || true)
    [ "$st" != "$seen" ] && { pull; seen="$st"; echo "$st" | tail -2; }
    if echo "$st" | grep -q -E "DONE|FAIL"; then break; fi
    echo "keep-alive caiu às $(date +%T); reconectando"; sleep 10
done
kill $PULLER 2>/dev/null; pull
colab stop -s "$SESSION"
colab usage | tail -3
echo "$st"
