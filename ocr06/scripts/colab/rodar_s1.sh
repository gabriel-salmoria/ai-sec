#!/usr/bin/env bash
# Drives session 1 from the PC: opens the L4, uploads the pack, starts sessao1.sh, keeps
# the kernel busy, copies results home after every finished step, and stops the VM at the
# end (DONE or FAIL), so nothing bills while idle.  Usage: scripts/colab/rodar_s1.sh PACK.tar.gz
set -uo pipefail
cd "$(dirname "$0")/../.."               # ocr06/
PACK="$1"; export SESSION=s1
C=scripts/colab/cssh
pull() { $C 'cd /content/ai-sec/ocr06 && tar -czf - experiments/paginas logs 2>/dev/null' | tar -xzf - -C . ; }
colab usage | tail -3
colab new -s "$SESSION" --gpu L4 || { echo "não abriu a L4"; exit 1; }
$C 'mkdir -p /content/ai-sec' && $C 'tar -xzf - -C /content/ai-sec' < "$PACK" || { echo "upload falhou"; colab stop -s "$SESSION"; exit 1; }
$C 'cd /content/ai-sec/ocr06 && nohup bash scripts/colab/sessao1.sh > /content/s1.out 2>&1 &'
( while sleep 600; do pull; done ) & PULLER=$!   # cópia a cada 10 min, além de a cada passo
seen=""
while true; do
    colab exec -s "$SESSION" -f scripts/colab/keepalive.py > logs/s1_keepalive_last.out 2>&1
    st=$($C 'cat /content/ai-sec/ocr06/logs/colab_status_s1 2>/dev/null' || true)
    [ "$st" != "$seen" ] && { pull; seen="$st"; echo "$st" | tail -2; }
    if echo "$st" | grep -q -E "DONE|FAIL"; then break; fi
    echo "keep-alive caiu às $(date +%T); reconectando"; sleep 10
done
kill $PULLER 2>/dev/null; pull
colab stop -s "$SESSION"
colab usage | tail -3
echo "$st"
