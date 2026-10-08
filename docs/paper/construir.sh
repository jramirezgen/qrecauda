#!/usr/bin/env bash
# Regenera docs/paper/paper.pdf desde paper.md con la plantilla propia (plantilla.tex) y el filtro (filtro.lua).
# Necesita pandoc y xelatex del sistema; no instala nada. Sin ellos, paper.md es la fuente completa y se lee tal cual.
# Las figuras (docs/paper/fig/) se regeneran aparte con: .venv/bin/python docs/paper/figuras.py
set -euo pipefail
cd "$(dirname "$0")"
command -v pandoc >/dev/null && command -v xelatex >/dev/null || { echo "faltan pandoc o xelatex: sólo se mantiene paper.md" >&2; exit 0; }
# El selector de variación U+FE0F no existe en las tipografías de LaTeX: se quita sólo en la copia temporal.
tmp="$(mktemp --suffix=.md --tmpdir=.)"
trap 'rm -f "$tmp"' EXIT
sed -e "s/\xef\xb8\x8f//g" paper.md > "$tmp"
pandoc "$tmp" -o paper.pdf --template=plantilla.tex --lua-filter=filtro.lua \
  --pdf-engine=xelatex --number-sections --listings
echo "paper.pdf regenerado"
