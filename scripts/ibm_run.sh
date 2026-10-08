#!/usr/bin/env bash
# Pasa QRECAUDA al ordenador cuántico de IBM, con un ensayo previo contra un backend falso.
#
#   scripts/ibm_run.sh ensayo                      # sin credencial ni cuota; escribe en salidas/ensayo_e4/ (NO es registro)
#   scripts/ibm_run.sh demo RUTA_TOKEN [BACKEND]   # la demo con una rama de hardware real (pocos disparos)
#   scripts/ibm_run.sh real RUTA_TOKEN [BACKEND]   # E4: 3 trabajos reales, a registro/corridas/
#
# RUTA_TOKEN es la RUTA de un fichero con el token (nunca el valor; nada se imprime). Tope de QPU por omisión: el de
# declaraciones/E4.toml (120 s para toda la corrida); cámbialo con MAX_SEGUNDOS_QPU=<s> (número finito, 0 < s <= 86400).
# El fichero del token debe tener modo 0600 (o 0400): `real` aborta si otros pueden leerlo (en discos de Windows, que no guardan
# permisos POSIX, avisa). Detalle: docs/HARDWARE.md.
set -euo pipefail
cd "$(dirname "$0")/.."

modo="${1:-}"
# Un array vacío con `set -u` falla en bash < 4.4 («unbound variable»): se expande con ${tope[@]+...} y funciona en todas.
tope=()
if [[ -n "${MAX_SEGUNDOS_QPU:-}" ]]; then
  # Sólo decimales simples: «nan», «inf», «1e12» o «-3» se rechazan aquí, antes de gastar nada (Python lo vuelve a comprobar).
  if ! [[ "$MAX_SEGUNDOS_QPU" =~ ^[0-9]+([.][0-9]+)?$ ]] || ! awk -v t="$MAX_SEGUNDOS_QPU" 'BEGIN { exit !(t > 0 && t <= 86400) }'; then
    echo "MAX_SEGUNDOS_QPU debe ser un número finito mayor que 0 y de hasta 86400 segundos, llegó: $MAX_SEGUNDOS_QPU" >&2
    exit 2
  fi
  tope=(--max-segundos-qpu "$MAX_SEGUNDOS_QPU")
fi
q() { uv run --no-sync qrecauda "$@"; }

token() {
  [[ -n "${1:-}" ]] || { echo "falta RUTA_TOKEN (ruta a un fichero con el token, no el token)" >&2; exit 2; }
  [[ -f "$1" ]] || { echo "no existe el fichero de token: $1" >&2; exit 2; }
}

# Permisos del fichero del token: 0600/0400 o nada. `real` aborta; `demo` avisa. En sistemas de ficheros que no guardan permisos POSIX
# (drvfs/9p/ntfs de WSL) el modo que se ve no significa nada: ahí sólo se avisa.
permisos() {
  local m fs
  m="$(stat -c %a "$1" 2>/dev/null || stat -f %Lp "$1" 2>/dev/null || echo "")"
  fs="$(stat -f -c %T "$1" 2>/dev/null || echo "")"
  [[ "$m" == "600" || "$m" == "400" || -z "$m" ]] && return 0
  case "$fs" in
    9p|v9fs|drvfs|ntfs|fuseblk|msdos|vfat|exfat|cifs|smb*)
      echo "AVISO: $1 está en un sistema de ficheros ($fs) sin permisos POSIX fiables (modo visto $m); guarda el token en un disco Linux con chmod 600." >&2
      return 0 ;;
  esac
  echo "el fichero de token $1 tiene modo $m y otros usuarios podrían leerlo: chmod 600 \"$1\"" >&2
  [[ "${2:-abortar}" == "avisar" ]] && return 0
  exit 3
}

case "$modo" in
  ensayo)
    rm -rf salidas/ensayo_e4   # un ensayo previo no debe mezclarse con éste
    q hardware --ensayo ${tope[@]+"${tope[@]}"}
    ;;
  demo)
    token "${2:-}"
    permisos "$2" avisar
    q demo --fuente ibm --token-file "$2" ${3:+--backend "$3"} ${tope[@]+"${tope[@]}"}
    ;;
  real)
    token "${2:-}"
    permisos "$2" abortar
    # La preinscripción debe estar commiteada y sin cambios: el juez lo comprueba, pero se avisa antes de gastar cuota.
    if [[ -n "$(git status --porcelain -- declaraciones/E4.toml docs/preinscripciones/E4.md)" ]]; then
      echo "declaraciones/E4.toml o docs/preinscripciones/E4.md tienen cambios sin commit: la corrida real no se permite" >&2
      exit 3
    fi
    q hardware --token-file "$2" ${3:+--backend "$3"} ${tope[@]+"${tope[@]}"}
    echo "Ahora: uv run --no-sync qrecauda juzgar E4"
    ;;
  *)
    sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//' >&2
    exit 2
    ;;
esac
