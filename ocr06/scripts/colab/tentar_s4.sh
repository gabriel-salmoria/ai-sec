#!/usr/bin/env bash
# Retries session 4 while Colab fails to hand over a G4 (nothing is billed on those failures),
# up to DEADLINE. Stops retrying on any other outcome, or if an assignment shows up after a
# failed request (possible orphan VM: needs a human look).
cd "$(dirname "$0")/../.."
P="$1"; DEADLINE=$(( $(date +%s) + ${2:-7200} )); n=0
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    n=$((n + 1)); echo "TENTATIVA $n $(date +%T)"
    : > logs/s4_keepalive_last.out
    scripts/colab/rodar_s4.sh "$P" > logs/s4_driver.log 2>&1 < /dev/null
    if ! grep -q "não abriu a G4" logs/s4_driver.log; then echo "SESSAO TERMINOU $(date +%T)"; exit 0; fi
    cp logs/s4_driver.log "logs/s4_driver_falha$n.log"
    if ! colab usage 2>/dev/null | grep -q "Active assignments: 0"; then
        echo "ALERTA: há máquina ativa depois de um pedido que falhou; parei as tentativas"; exit 2; fi
    echo "FALHOU $n $(date +%T) ($(grep -oE 'Bad Gateway|Read timed out|[A-Z][a-z]+ [A-Z][a-z]+$' logs/s4_driver.log | tail -1)); nada cobrado"
    sleep 600
done
echo "DESISTI $(date +%T): sem G4 em 2 h"
exit 3
