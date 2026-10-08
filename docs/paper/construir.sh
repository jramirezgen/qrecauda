#!/usr/bin/env bash
# Regenera docs/paper/paper.pdf desde paper.md. Necesita pandoc y xelatex (ya instalados en el sistema; no instala nada).
# Sin ellos, paper.md es la fuente completa y se lee tal cual.
set -euo pipefail
cd "$(dirname "$0")"
command -v pandoc >/dev/null && command -v xelatex >/dev/null || { echo "faltan pandoc o xelatex: sólo se mantiene paper.md" >&2; exit 0; }
# El selector de variación U+FE0F no existe en las tipografías de LaTeX: se quita sólo en la copia temporal.
tmp="$(mktemp --suffix=.md)"
trap 'rm -f "$tmp"' EXIT
sed -e "s/\xef\xb8\x8f//g" -e "s/⚠/(!)/g" paper.md > "$tmp"
pandoc "$tmp" -o paper.pdf --pdf-engine=xelatex --toc \
  -V mainfont="DejaVu Serif" -V sansfont="DejaVu Sans" -V monofont="DejaVu Sans Mono" \
  -V geometry:margin=2.4cm -V fontsize=10pt -V colorlinks=true -V lang=es
echo "paper.pdf regenerado"
