# Funções de saída usadas pelos scripts (cores só se o terminal suportar).
if [ -t 1 ]; then B=$'\e[1m'; G=$'\e[32m'; Y=$'\e[33m'; R=$'\e[31m'; N=$'\e[0m'; else B= G= Y= R= N=; fi
titulo() { printf '\n%s== %s%s\n' "$B" "$1" "$N"; }
ok()     { printf '  %s✓%s %s\n' "$G" "$N" "$1"; }
aviso()  { printf '  %s!%s %s\n' "$Y" "$N" "$1"; }
erro()   { printf '  %s✗%s %s\n' "$R" "$N" "$1" >&2; }
