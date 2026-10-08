#!/usr/bin/env bash
# Pasa QRECAUDA al ordenador cuántico de IBM, con un ensayo previo contra un backend falso.
#
#   scripts/ibm_run.sh ensayo                      # sin credencial ni cuota; escribe en salidas/ensayo_e4/ (NO es registro)
#   scripts/ibm_run.sh demo RUTA_TOKEN [BACKEND]   # la demo con una rama de hardware real (pocos disparos)
#   scripts/ibm_run.sh real RUTA_TOKEN [BACKEND]   # E4: 3 trabajos reales, a registro/corridas/
#
# RUTA_TOKEN es la RUTA de un fichero con el token (nunca el valor; nada se imprime). Tope de QPU por omisión: el de
# declaraciones/E4.toml (120 s para toda la corrida); cámbialo con MAX_SEGUNDOS_QPU=<s>. Detalle: docs/HARDWARE.md.
set -euo pipefail
cd "$(dirname "$0")/.."

modo="${1:-}"
tope=()
[[ -n "${MAX_SEGUNDOS_QPU:-}" ]] && tope=(--max-segundos-qpu "$MAX_SEGUNDOS_QPU")
q() { uv run qrecauda "$@"; }

token() {
  [[ -n "${1:-}" ]] || { echo "falta RUTA_TOKEN (ruta a un fichero con el token, no el token)" >&2; exit 2; }
  [[ -f "$1" ]] || { echo "no existe el fichero de token: $1" >&2; exit 2; }
}

case "$modo" in
  ensayo)
    rm -rf salidas/ensayo_e4   # un ensayo previo no debe mezclarse con éste
    q hardware --ensayo "${tope[@]}"
    ;;
  demo)
    token "${2:-}"
    q demo --fuente ibm --token-file "$2" ${3:+--backend "$3"} "${tope[@]}"
    ;;
  real)
    token "${2:-}"
    # La preinscripción debe estar commiteada y sin cambios: el juez lo comprueba, pero se avisa antes de gastar cuota.
    if [[ -n "$(git status --porcelain -- declaraciones/E4.toml docs/preinscripciones/E4.md)" ]]; then
      echo "declaraciones/E4.toml o docs/preinscripciones/E4.md tienen cambios sin commit: la corrida real no se permite" >&2
      exit 3
    fi
    q hardware --token-file "$2" ${3:+--backend "$3"} "${tope[@]}"
    echo "Ahora: uv run qrecauda juzgar E4"
    ;;
  *)
    sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//' >&2
    exit 2
    ;;
esac
