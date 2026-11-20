#!/usr/bin/env bash
# Drives session 4 from the PC: opens the GPU, uploads code and data, starts sessao4.sh,
# keeps the kernel busy, copies results home, and stops the machine at the end.
#   scripts/colab/rodar_s4.sh /path/ocr06_s4 [G4|A100]
#
# Guard rules (the guards must never be the problem):
#  1. Never stop the machine because a reading failed or is unknown; act only on confirmed facts.
#  2. Before any stop after the work started, copy everything home and check it arrived
#     (bounded retries, so a broken connection can't keep a paid machine waiting for long).
#  3. Automatic stops only when: the session finished (DONE/FAIL); the session never started
#     (nothing to save); or the balance is confirmed below FLOOR in two readings in a row
#     (at 0 Colab would kill the machine without saving anything).
#  4. The hourly rate is only logged and reported, never used to stop.
set -uo pipefail
cd "$(dirname "$0")/../.."               # ocr06/
P="$1"; GPU="${2:-G4}"; export SESSION=s4; FLOOR=2.0; RESERVE=5.0
C="flock /tmp/ocr06_s4_ssh.lock scripts/colab/cssh"   # one ssh at a time (Colab refuses a 2nd: HTTP 429)
R=/content/ai-sec/ocr06
saldo() { colab usage 2>/dev/null | grep -oE "balance: [0-9.]+" | grep -oE "[0-9.]+$"; }
taxa() { colab usage 2>/dev/null | grep -oE "rate: [0-9.]+" | grep -oE "[0-9.]+$"; }
status() { timeout 60 $C "cat $R/logs/colab_status_s4 2>/dev/null" < /dev/null; }
pull() {  # pull [ck]: logs, test outputs, lora_v2 summaries + adapter (+ latest checkpoint with "ck")
    local ck=""
    [ "${1:-}" = ck ] && ck='$(ls -d models/lora_v2/checkpoints/checkpoint-* 2>/dev/null | sort -V | tail -1)'
    timeout 300 $C "cd $R && tar -czf - logs experiments/paginas \$(ls models/lora_v2/*.json 2>/dev/null) \$(ls -d models/lora_v2/adapter 2>/dev/null) $ck 2>/dev/null" < /dev/null | tar -xzf - -C . 2>/dev/null
}
save_final() {  # copies home and checks: adapter size matches, every remote output file exists here
    for i in 1 2 3; do
        pull
        local ok=1 rem rs ls_
        rem=$(timeout 60 $C "cd $R && ls experiments/paginas/*/*.jsonl 2>/dev/null; stat -c %s models/lora_v2/adapter/adapter_model.safetensors 2>/dev/null || echo 0; echo FIM" < /dev/null)
        echo "$rem" | grep -q "^FIM$" || ok=0
        rs=$(echo "$rem" | grep -B1 "^FIM$" | head -1)
        ls_=$(stat -c %s models/lora_v2/adapter/adapter_model.safetensors 2>/dev/null || echo 0)
        [ "$rs" = "$ls_" ] || ok=0
        for f in $(echo "$rem" | grep "\.jsonl$"); do [ -s "$f" ] || ok=0; done
        [ $ok = 1 ] && { echo "SALVO E CONFERIDO $(date +%T)"; return 0; }
        echo "cópia final incompleta (tentativa $i) $(date +%T); repetindo"; sleep 20
    done
    echo "AVISO: cópia final não conferida após 3 tentativas $(date +%T)"; return 1
}
confirma_inicio() {  # status file via ssh, else via the kernel; 0 = started, 1 = confirmed not started, 2 = unknown
    for _ in 1 2 3 4 5 6; do status | grep -q "START gpu_check" && return 0; sleep 20; done
    cat > /tmp/ver_s4.py <<PY
import os; p="$R/logs/colab_status_s4"; print("STATUS:" + (open(p).read() if os.path.exists(p) else "VAZIO"))
PY
    local out; out=$(timeout 90 colab exec -s "$SESSION" -f /tmp/ver_s4.py 2>/dev/null)
    echo "$out" | grep -q "START gpu_check" && return 0
    echo "$out" | grep -q "STATUS:VAZIO" && return 1
    return 2
}

colab usage | tail -3
COLAB_CLI_REQUEST_TIMEOUT=900 colab new -s "$SESSION" --gpu "$GPU" || { echo "não abriu a $GPU"; exit 1; }
sleep 20; echo "TAXA $GPU: $(taxa) UC/h"
ok=0
for i in 1 2 3; do
    timeout 600 $C 'mkdir -p /content/ai-sec && tar -xzf - -C /content/ai-sec' < "${P}_code.tar.gz" && { ok=1; break; }
    echo "envio do código falhou (tentativa $i)"; sleep 20
done
[ $ok = 1 ] || { echo "código não subiu: desligando (nada a salvar)"; colab stop -s "$SESSION"; exit 1; }
cat > /tmp/start_s4.py <<PY
import subprocess
subprocess.Popen("bash scripts/colab/sessao4.sh > /content/s4.out 2>&1", shell=True,
                 start_new_session=True, stdin=subprocess.DEVNULL, cwd="$R")
print("sessao4 iniciada")
PY
timeout 90 colab exec -s "$SESSION" -f /tmp/start_s4.py
confirma_inicio; c=$?
if [ $c != 0 ]; then
    echo "início não confirmado pelo kernel; tentando por ssh"
    timeout 40 $C "cd $R && (setsid nohup bash scripts/colab/sessao4.sh > /content/s4.out 2>&1 < /dev/null &)" < /dev/null
    confirma_inicio; c=$?
fi
case $c in
    0) echo "sessao4 confirmada $(date +%T)" ;;
    1) echo "sessao4 não iniciou (confirmado): desligando (nada a salvar)"; colab stop -s "$SESSION"; exit 1 ;;
    2) echo "sem contato com a máquina para confirmar; seguindo (o keep-alive mostrará o estado)" ;;
esac
ok=0
for i in 1 2 3; do
    timeout 1800 $C "tar -xzf - -C /content/ai-sec && touch $R/data/.upload_ok" < "${P}_data.tar.gz" && { ok=1; break; }
    echo "envio dos dados falhou (tentativa $i)"; sleep 30
done
[ $ok = 1 ] || { echo "dados não subiram após 3 tentativas: salvando logs e desligando"; pull; colab stop -s "$SESSION"; exit 1; }

( while sleep 600; do  # copies home every 10 min; during training also the latest checkpoint
    if status | grep -q "^START train" && ! status | grep -q "^OK train"; then pull ck; else pull; fi
  done ) & PULLER=$!
( baixo=0; while sleep 120; do  # balance floor (confirmed twice) + base FP8 gate; rate only logged
    b=$(saldo); r=$(taxa)
    echo "$(date +%T) saldo ${b:-?} taxa ${r:-?}" >> logs/s4_saldo.log
    st=$(status || true)
    if echo "$st" | grep -q "^START gate_basefp8" && ! echo "$st" | grep -qE "^(OK|STOP) gate_basefp8"; then
        # optional step: runs only with a confirmed balance that keeps the reserve; unknown = skip
        if [ -n "$b" ] && awk "BEGIN{exit !($b - 2.8 >= $RESERVE)}"; then timeout 40 $C "touch $R/data/.gate_basefp8" < /dev/null; echo "base FP8 liberado (saldo $b)"
        else timeout 40 $C "touch $R/data/.parar" < /dev/null; echo "base FP8 pulado (saldo ${b:-?})"; fi
    fi
    [ -z "$b" ] && continue
    if awk "BEGIN{exit !($b < $FLOOR)}"; then baixo=$((baixo + 1)); else baixo=0; fi
    if [ $baixo -ge 2 ]; then
        echo "saldo $b abaixo de $FLOOR em duas leituras: salvando e desligando"
        save_final; colab stop -s "$SESSION"; break
    fi
  done ) & GUARD=$!
seen=""
while true; do
    timeout 14400 colab exec -s "$SESSION" -f scripts/colab/keepalive_s4.py > logs/s4_keepalive_last.out 2>&1
    st=$(status || true)
    [ -n "$st" ] && [ "$st" != "$seen" ] && { pull; seen="$st"; echo "$st" | tail -2; }
    if echo "$st" | grep -q -E "DONE|FAIL"; then break; fi
    if colab usage 2>/dev/null | grep -q "Active assignments: 0"; then echo "máquina já parada $(date +%T)"; break; fi
    echo "keep-alive caiu às $(date +%T); reconectando"; sleep 10
done
kill $PULLER $GUARD 2>/dev/null
colab usage 2>/dev/null | grep -q "Active assignments: 0" || save_final
colab stop -s "$SESSION"
colab usage | tail -3
echo "$st"
