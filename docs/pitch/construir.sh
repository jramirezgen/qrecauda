#!/usr/bin/env bash
# Regenera docs/pitch/deck.pdf desde DECK.md (pandoc + beamer + xelatex del sistema; no instala nada).
# La figura se regenera aparte: .venv/bin/python presentacion/figura_demo.py
# En la copia temporal se quitan los marcadores {{...}} (sólo sirven para cruzar cifras con el registro),
# el rótulo «Lámina N · » del título y el selector de variación U+FE0F.
set -euo pipefail
cd "$(dirname "$0")"
command -v pandoc >/dev/null && command -v xelatex >/dev/null || { echo "faltan pandoc o xelatex: sólo se mantiene DECK.md" >&2; exit 0; }
tmp="$(mktemp --suffix=.md --tmpdir=.)"
trap 'rm -f "$tmp"' EXIT
sed -e "s/\xef\xb8\x8f//g" -e 's/{{[^{}]*}}//g' -e 's/^# Lámina [0-9]* · /# /' -e 's/{\.fig}/{height=40%}/' -e '/^<!--$/,/^-->$/d' DECK.md > "$tmp"
pandoc "$tmp" -o deck.pdf -t beamer --slide-level=1 --pdf-engine=xelatex \
  -V aspectratio=169 -V theme=default -V colortheme=seahorse -V fontsize=11pt \
  -V mainfont="TeX Gyre Heros" -V monofont="DejaVu Sans Mono" -V lang=es \
  -V 'header-includes=\setbeamertemplate{navigation symbols}{}\setbeamertemplate{footline}[frame number]'
echo "deck.pdf regenerado"
