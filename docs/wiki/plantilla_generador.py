# -*- coding: utf-8 -*-
"""Plantilla de generador de canvas. Copiar a `<repo>/docs/canvas/generar_X.py`.

Reglas que esta plantilla ya cumple, y que no hay que volver a decidir:
  · el canvas se GENERA (este fichero es la fuente, el `.canvas` es el artefacto)
  · no se escribe si la compuerta de legibilidad no pasa
  · toda cifra de un nodo se mide antes; la que falta se NOMBRA, no se rellena
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from canvas_lib import Lienzo, informe   # noqa: E402  (vendorizado)

L = Lienzo()                 # paso 1400 · ancho 620 · padding 60 · gap 110
C = L.columnas("leyenda", "entrada", "proceso", "salida", desde=-1400)

# ── leyenda: fuera de todo grupo a proposito ────────────────────────────────
L.nodo("leyenda", C["leyenda"], -900, L.ancho, 300, """## <PROYECTO> — <qué mapea>
*<rama · corrida · fecha de las cifras>*

🟪 arquitectura · 🟦 dato de entrada · 🟨 compuerta · 🟩 verde hoy
🟧 publicado sin voto · 🟥 hueco o interruptor apagado""", "6")

# ── una columna, apilada ────────────────────────────────────────────────────
p = L.pila("entrada", -900)
p.add("in_1", 220, "## 1 · <material>\n`<fichero>` — **<cifra medida>**\n\n<qué papel juega>", "5")
p.add("in_2", 200, "## 2 · <material>\n…", "5")
p.cerrar("g_entrada", "LO QUE ENTRA — y con qué papel", color="5")

q = L.pila("proceso", -900)
q.add("pr_1", 220, "## <fase>\n`<módulo>` — <qué hace>\n\n<parámetros con su valor>", "4")
q.cerrar("g_proceso", "EL MOTOR", color="4")

# ── una banda horizontal (varias columnas) ──────────────────────────────────
# L.envolver("g_deuda", "LO QUE HOY NO CIERRA", ["d1", "d2"], color="1")

L.arista("in_1", "pr_1", "right", "left", "<qué viaja por esta flecha>")

out = sys.argv[1] if len(sys.argv) > 1 else "mi_mapa.canvas"
ok, lineas = informe(L.a_dict(), libres={"leyenda"})
for l in lineas:
    print("  " + l)
if not ok:
    raise SystemExit("✗ no se escribe un canvas con etiquetas ilegibles")
L.escribir(out)
print(f"→ {out}  (corredor entre columnas: {L.corredor()} px)")
