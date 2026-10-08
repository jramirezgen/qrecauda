# -*- coding: utf-8 -*-
"""Construye docs/pitch/QRecauda_pitch.pptx: nueve láminas de exposición y dos de respaldo, en 16:9.

Formato: fondo crema, títulos de acción en Georgia, cuerpo en Calibri, filetes finos, cifras grandes con su rótulo,
gráfico nativo editable y notas del orador. Las cifras proceden de docs/pitch/DECK.md (que las ata al registro) y de
docs/pitch/IMPACTO.md (contexto, con su etiqueta). Ninguna cifra nueva nace aquí.

    uv run --with python-pptx python docs/pitch/construir_pptx.py
"""
from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

AQUI = Path(__file__).resolve().parent
SALIDA = AQUI / "QRecauda_pitch.pptx"
FIGURA = AQUI / "fig" / "demo_tres_ramas.png"

FONDO, TINTA, GRIS = RGBColor(0xFB, 0xF9, 0xF5), RGBColor(0x2B, 0x28, 0x24), RGBColor(0x7A, 0x75, 0x6C)
VERDE, OXIDO, FILETE = RGBColor(0x2E, 0x5E, 0x4E), RGBColor(0x9C, 0x3D, 0x2A), RGBColor(0xD9, 0xD4, 0xCA)
PIE = "kaitokid · QRecauda · Hackatón Qiskit IBM Lima, Track 4"

prs = Presentation()
prs.slide_width, prs.slide_height = Emu(12191695), Emu(6858000)
BLANCO = prs.slide_layouts[6]


def texto(s, x, y, w, h, t, *, fuente="Calibri", tam=15, color=TINTA, negrita=False, alinea=PP_ALIGN.LEFT, ancla=MSO_ANCHOR.TOP):
    cj = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = cj.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = ancla
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    lineas = t if isinstance(t, list) else [t]
    for i, ln in enumerate(lineas):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = alinea
        if i:
            p.space_before = Pt(6)
        r = p.add_run()
        r.text = ln
        r.font.name, r.font.size, r.font.bold = fuente, Pt(tam), negrita
        r.font.color.rgb = color
    return cj


def filete(s, x, y, w, color=FILETE, grosor=0.012):
    r = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(grosor))
    r.fill.solid()
    r.fill.fore_color.rgb = color
    r.line.fill.background()
    return r


def lamina(titulo, n, notas=""):
    s = prs.slides.add_slide(BLANCO)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = FONDO
    texto(s, 0.7, 0.55, 11.9, 0.9, titulo, fuente="Georgia", tam=26)
    filete(s, 0.7, 1.66, 11.95)
    filete(s, 0.7, 7.0, 11.95)
    texto(s, 0.7, 7.05, 8.0, 0.3, PIE, tam=10, color=GRIS)
    texto(s, 12.0, 7.05, 0.65, 0.3, str(n), tam=10, color=GRIS, alinea=PP_ALIGN.RIGHT)
    if notas:
        s.notes_slide.notes_text_frame.text = notas
    return s


def cifra(s, x, y, w, grande, rotulo, color=TINTA, tam=40):
    texto(s, x, y, w, 0.85, grande, fuente="Georgia", tam=tam, color=color)
    texto(s, x, y + 0.85, w, 0.7, rotulo, tam=13, color=GRIS)


def tabla(s, x, y, w, filas, anchos, *, alto_fila=0.5, tam=13):
    t = s.shapes.add_table(len(filas), len(filas[0]), Inches(x), Inches(y), Inches(w), Inches(alto_fila * len(filas))).table
    for j, a in enumerate(anchos):
        t.columns[j].width = Inches(a)
    for i, fila in enumerate(filas):
        for j, v in enumerate(fila):
            c = t.cell(i, j)
            c.fill.solid()
            c.fill.fore_color.rgb = TINTA if i == 0 else (FONDO if i % 2 else RGBColor(0xF3, 0xEF, 0xE7))
            c.margin_left = c.margin_right = Inches(0.1)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf = c.text_frame
            tf.word_wrap = True
            r = tf.paragraphs[0].add_run()
            r.text = v
            r.font.name, r.font.size = "Calibri", Pt(tam)
            r.font.bold = i == 0 or j == 0
            r.font.color.rgb = FONDO if i == 0 else (OXIDO if "NO CUMPLE" in v else TINTA)
    return t


# ── 1 · portada ────────────────────────────────────────────────────────────────────────────────
s = prs.slides.add_slide(BLANCO)
s.background.fill.solid()
s.background.fill.fore_color.rgb = FONDO
texto(s, 1.1, 0.55, 11.0, 0.4, "HACKATÓN QISKIT IBM LIMA · TRACK 4", tam=15, color=GRIS, negrita=True)
texto(s, 1.1, 0.95, 11.0, 0.4, "Criptoseguridad para recaudación mediante generación cuántica de números aleatorios", tam=13, color=GRIS)
texto(s, 1.1, 1.75, 11.5, 2.3, "QRecauda: claves de cifrado para peajes y Metro, medidas desde la fuente hasta la clave", fuente="Georgia", tam=38)
texto(s, 1.1, 4.25, 11.0, 0.6, "Un pipeline sobre Qiskit con cinco experimentos preinscritos y un resultado negativo publicado", tam=20, color=GRIS)
filete(s, 1.1, 5.3, 11.0, TINTA, 0.01)
texto(s, 1.1, 5.5, 8.0, 0.45, "kaitokid", tam=22, negrita=True)
texto(s, 1.1, 6.0, 10.0, 0.4, "Preselección · versión 0.2.0 · octubre de 2026 · código abierto (Apache-2.0)", tam=15, color=GRIS)
s.notes_slide.notes_text_frame.text = "Diez segundos. «La aleatoriedad clásica se predice. La recaudación del Perú no debería.»"

# ── 2 · problema ───────────────────────────────────────────────────────────────────────────────
s = lamina("Una clave que se puede recalcular no protege un cobro", 2,
           "El volumen es real; la exigencia legal de un QRNG, no. Ninguna norma revisada (Ley 29733, SBS, MTC) la pide. "
           "El argumento es de ingeniería: un generador pseudoaleatorio sale de un estado, y quien lo reconstruye reproduce las claves siguientes. "
           "Cifras de contexto: docs/pitch/IMPACTO.md, con etiqueta verificado o tercero.")
cifra(s, 0.9, 1.93, 3.7, "203,9 M", "pasajeros en la Línea 1 del Metro de Lima en 2025 (verificado)")
cifra(s, 0.9, 3.63, 3.7, "600 000", "usuarios por día en la Línea 1 (dato de tercero)", VERDE, 38)
cifra(s, 0.9, 5.33, 3.7, "24,6 M", "vehículos en peajes, primer cuatrimestre de 2021 (tercero, desactualizado)", OXIDO, 34)
filete(s, 0.7, 3.55, 3.9)
filete(s, 0.7, 5.25, 3.9)
texto(s, 5.2, 1.93, 7.3, 0.4, "Qué está en juego", tam=14, negrita=True)
texto(s, 5.2, 2.45, 7.3, 4.2, [
    "Cada transacción pequeña se cifra con una clave y un nonce que salen de un generador.",
    "Un generador pseudoaleatorio calcula su salida desde un estado interno. Quien lo roba o lo reconstruye reproduce las claves futuras.",
    "Un generador cuántico evita esa dependencia, pero uno simulado no aporta entropía cuántica, y aprobar una batería estadística no prueba el origen.",
    "Pregunta del proyecto: ¿qué calidad tiene la clave que sale de toda la cadena, y cómo se mide sin engañarse?",
], tam=16, color=GRIS)

# ── 3 · solución ───────────────────────────────────────────────────────────────────────────────
s = lamina("Una cadena que mide cada etapa, de los bits a la clave", 3,
           "Fuente: un circuito de un solo gate (Hadamard) sobre ocho qubits. Hoy en el simulador Aer; la computadora de IBM entra por el mismo puerto. "
           "Siete métricas de aceptación con umbral escrito antes de correr. Aer es pseudoaleatorio: con semilla es determinista y no tiene valor de seguridad.")
etapas = [("Fuente de bits", "Hadamard × 8 qubits"), ("Mitigación", "twirling de lectura"), ("Extracción", "Peres"),
          ("Hash", "Toeplitz + LHL"), ("Validación", "NIST 800-22 y 90B"), ("Cifrado", "AES-256-GCM")]
for i, (a, b) in enumerate(etapas):
    x = 0.9 + i * 1.95
    texto(s, x, 2.15, 1.75, 0.5, f"0{i + 1}", fuente="Georgia", tam=26, color=VERDE if i != 4 else OXIDO)
    texto(s, x, 2.7, 1.75, 0.5, a, tam=17, negrita=True)
    texto(s, x, 3.2, 1.75, 0.7, b, tam=13, color=GRIS)
    filete(s, x - 0.1, 2.05, 1.8, FILETE)
texto(s, 0.9, 4.45, 3.7, 0.9, "M1–M7", fuente="Georgia", tam=44)
texto(s, 0.9, 5.3, 3.7, 0.7, "siete métricas de aceptación: sesgo, min-entropía, tres pruebas NIST, tasa y latencia", tam=13, color=GRIS)
texto(s, 5.2, 4.55, 7.3, 2.2, [
    "La fuente es un puerto: cambiar de simulador a hardware de IBM no toca el resto.",
    "La mitigación de lectura conserva los bits por disparo; ZNE y PEC no lo hacen.",
    "Toda cifra sale de una corrida con nombre; lo no verificado se marca como hipótesis.",
], tam=15, color=GRIS)

# ── 4 · hallazgo ───────────────────────────────────────────────────────────────────────────────
s = lamina("La batería estadística aprueba claves de fuentes defectuosas; medirlas por la fuente las corrige", 4,
           "Hallazgo central. Control negativo del pipeline completo (E5): tres fuentes con dependencia entre bits atraviesan la cadena. "
           "Con el dimensionado de la 0.1.0 las nueve claves pasan M1 a M5 y salen entre 1,2 y 2,5 veces más largas de lo que la fuente sostiene. "
           "El dimensionado conservador las acorta bajo el techo teórico. Límite honesto: E5 es casi un control por construcción y el conservador es opcional. "
           "Valores del gráfico: fuente markov_fuerte, media de tres semillas (C.E5), en miles de bits; techo teórico 231 944 bits.")
cd = CategoryChartData()
cd.categories = ["MCV (0.1.0)", "mín. de MCV y 90B", "conservador"]
cd.add_series("clave obtenida (miles de bits)", (381, 279, 56))
cd.add_series("techo teórico de la fuente", (232, 232, 232))
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(5.0), Inches(2.3), Inches(7.55), Inches(4.4), cd)
ch = gf.chart
ch.has_legend = True
ch.legend.position, ch.legend.include_in_layout = XL_LEGEND_POSITION.BOTTOM, False
ch.legend.font.size, ch.legend.font.name = Pt(12), "Calibri"
ch.font.size, ch.font.name = Pt(12), "Calibri"
for ser, col in zip(ch.plots[0].series, (VERDE, OXIDO)):
    ser.format.fill.solid()
    ser.format.fill.fore_color.rgb = col
ch.plots[0].has_data_labels = True
ch.plots[0].data_labels.font.size = Pt(12)
ch.plots[0].data_labels.number_format = '0'
ch.plots[0].data_labels.number_format_is_linked = False
ch.value_axis.has_major_gridlines = False
ch.value_axis.visible = False
texto(s, 5.1, 1.93, 7.4, 0.4, "Fuente de Markov fuerte: bits de clave según el dimensionado", tam=14, negrita=True)
cifra(s, 0.9, 1.93, 3.7, "1,2 a 2,5×", "más larga que lo que la fuente sostiene, con claves que pasan M1 a M5", OXIDO, 36)
cifra(s, 0.9, 3.63, 3.7, "56 mil", "bits con el dimensionado conservador, bajo el techo de 232 mil", VERDE, 38)
cifra(s, 0.9, 5.33, 3.7, "89,5–92,3 %", "de la clave se conserva con una fuente buena", TINTA, 32)
filete(s, 0.7, 3.55, 3.9)
filete(s, 0.7, 5.25, 3.9)

# ── 5 · demo ───────────────────────────────────────────────────────────────────────────────────
s = lamina("Demo: la mitigación limpia la entrada, y la clave pasa aun sin ella", 5,
           "qrecauda demo corre las tres ramas: PRNG, Aer sin mitigar, Aer mitigado. Sesgo de la muestra: sin mitigar 0,0296 a 0,0304 (umbral 0,01); mitigado a lo sumo 0,0004. "
           "La clave pasa M1 en las tres ramas: pasar la batería no prueba el origen. Lo digo yo antes de que lo pregunten.")
s.shapes.add_picture(str(FIGURA), Inches(0.7), Inches(1.95), width=Inches(7.6))
cifra(s, 8.8, 1.93, 3.8, "0,030 → 0,0004", "sesgo de lectura de la muestra, sin y con mitigación (umbral 0,01)", VERDE, 30)
cifra(s, 8.8, 3.63, 3.8, "3 de 3", "semillas en que la clave sin mitigar también pasa M1", OXIDO, 36)
texto(s, 8.8, 5.45, 3.8, 1.4, "Con el simulador, la semilla es pública: esta clave se puede recalcular y no tiene valor de seguridad.", tam=13, color=GRIS)
filete(s, 8.7, 3.55, 3.9)
filete(s, 8.7, 5.35, 3.9)

# ── 6 · validación ─────────────────────────────────────────────────────────────────────────────
s = lamina("Cinco experimentos juzgados, uno de ellos negativo, y uno bloqueado", 6,
           "E1, E2, E3b y E5 cumplen, con matices declarados: poder limitado para fallar. E3 no cumplió y su veredicto sigue en el registro. "
           "E4, sobre hardware de IBM, está preinscrito y bloqueado por falta de credencial.")
tabla(s, 0.7, 1.95, 11.95, [
    ["experimento", "veredicto", "qué dice"],
    ["E1 · calidad de la clave", "CUMPLE, condicionado", "clave de al menos 956,6 mil bits; condicionado a dos enmiendas fechadas"],
    ["E2 · sesgo de lectura", "CUMPLE", "el twirling baja el sesgo de 0,030 a casi cero; ZNE y PEC no lo mueven"],
    ["E3 · latencia por transacción", "NO CUMPLE", "tasa correcta (180 a 195 kbit/s), latencia p95 de 5,5 a 9,4 s frente a 500 ms"],
    ["E3b · reserva de claves", "CUMPLE", "p95 de 0,17 a 0,18 ms con la reserva cebada; otro diseño, no comparable con E3"],
    ["E5 · control negativo", "CUMPLE", "el pipeline completo acorta claves de fuentes defectuosas; casi un control por construcción"],
    ["E4 · hardware de IBM", "PENDIENTE", "preinscrito; espera una credencial de IBM Quantum"],
], [3.3, 2.5, 6.15], alto_fila=0.62, tam=14)

# ── 7 · latencia ───────────────────────────────────────────────────────────────────────────────
s = lamina("Generar una clave por transacción tarda segundos; una reserva de claves la deja en décimas de milisegundo", 7,
           "E3 mide generar y cifrar dentro de la transacción: p95 de 5,5 a 9,4 s, entre 11 y 19 veces el umbral. El veredicto no se reabre. "
           "E3b es otro diseño con su propia preinscripción: un proceso productor genera claves aparte. p95 de 0,17 a 0,18 ms con la reserva cebada, 12 000 transacciones por semilla, cero esperas. "
           "No es comparable con E3. El costo se trasladó al arranque: 6,6 s hasta la primera clave, y una transacción que llegue durante él incumpliría M7. "
           "Límites: simulador, sin la cola ni la red de IBM, demanda declarada por el equipo.")
cifra(s, 0.9, 1.93, 5.4, "5,5 a 9,4 s", "E3: una clave nueva por transacción (p95), frente al umbral M7 de 500 ms", OXIDO, 44)
cifra(s, 6.9, 1.93, 5.6, "0,17 a 0,18 ms", "E3b: clave tomada de la reserva ya cebada (p95)", VERDE, 44)
filete(s, 0.7, 3.75, 5.6)
filete(s, 6.7, 3.75, 5.9)
texto(s, 0.9, 4.0, 5.4, 2.8, [
    "La tasa de claves supera 18 veces el umbral: el sistema produce rápido y entrega tarde.",
    "El 75 % del ciclo se va en simular el circuito y en la mitigación.",
], tam=16, color=GRIS)
texto(s, 6.9, 4.0, 5.6, 2.8, [
    "Capacidad del productor de 177 a 199 kbit/s; entregado en régimen, 47,8 kbit/s; cero esperas.",
    "El costo pasa al arranque (6,6 s hasta la primera clave) y a la custodia de una reserva en memoria.",
    "Medido en simulador, sin la cola ni la red de IBM.",
], tam=16, color=GRIS)

# ── 8 · calidad ────────────────────────────────────────────────────────────────────────────────
s = lamina("La calidad se puede auditar: cada cifra se regenera desde un registro que sólo crece", 8,
           "883 casos de prueba, siete contratos de importación ejecutables, dos validadores independientes que se contrastan. "
           "Cada experimento se preinscribe antes de correr; un juez se niega a veredictar si falta el orden o un control. "
           "Dos revisiones adversariales independientes (R.01 y R.02) puntuaron entre 5,5 y 7,5 sobre 10 y sus hallazgos están incorporados. "
           "El plan como grafo verificable y la documentación son material suplementario compartido.")
cifra(s, 0.9, 1.93, 3.7, "883", "casos de prueba; CI verde en un entorno limpio", TINTA, 44)
cifra(s, 0.9, 3.63, 3.7, "7", "contratos de importación que protegen el dominio", VERDE, 44)
cifra(s, 0.9, 5.33, 3.7, "79", "nodos en el plan verificable, con estado en un registro de sólo añadir", OXIDO, 40)
filete(s, 0.7, 3.55, 3.9)
filete(s, 0.7, 5.25, 3.9)
texto(s, 5.2, 1.93, 7.3, 0.4, "Cómo se evita engañarse", tam=14, negrita=True)
texto(s, 5.2, 2.45, 7.3, 4.3, [
    "Umbrales, controles y desenlaces posibles se escriben antes de correr; las enmiendas llevan fecha y commit.",
    "Cada experimento lleva controles que pueden invalidar la corrida; un generador clásico también pasa la batería, y eso se mide.",
    "Dos revisiones independientes buscaron romper el trabajo; sus hallazgos corrigieron frases que prometían más de lo medido.",
    "Un resultado negativo (E3) se conserva en el registro y no se reabre; el rediseño es otro experimento.",
], tam=16, color=GRIS)

# ── 9 · hoja de ruta y petición ────────────────────────────────────────────────────────────────
s = lamina("Del simulador al hardware: lo que falta es una corrida real en IBM", 9,
           "TRL del sistema: 3. Todo se midió en simulador y no se afirma origen cuántico. El camino a IBM está implementado y ensayado contra un backend falso; "
           "la corrida real (E4) está preinscrita y espera una credencial. Pedimos acceso a un backend de IBM Quantum, y que quien opere el cobro revise los umbrales de tasa y latencia, que hoy son del equipo.")
tabla(s, 0.7, 1.95, 7.0, [
    ["etapa", "qué la cierra"],
    ["Hoy · TRL 3", "simulador; latencia resuelta con reserva; sin hardware"],
    ["TRL 4", "corrida real en IBM con identificador de trabajo (E4)"],
    ["TRL 5", "E1 y E2 repetidos sobre la fuente real"],
    ["Piloto", "umbrales validados con quien opere el cobro"],
    ["Producción", "custodia de claves y certificación de la fuente"],
], [1.9, 5.1], alto_fila=0.62, tam=14)
texto(s, 8.2, 1.93, 4.4, 0.4, "Lo que pedimos", tam=14, negrita=True)
texto(s, 8.2, 2.45, 4.4, 2.6, [
    "Acceso a un backend de IBM Quantum para la primera corrida real.",
    "Que quien opere el cobro revise los umbrales de 500 ms y 10 kbit/s.",
], tam=16, color=GRIS)
texto(s, 8.2, 5.1, 4.4, 1.6, "Con hardware real no diríamos «entropía cuántica certificada»: no existe un QRNG certificado de IBM que podamos citar.", tam=13, color=OXIDO)

# ── 10 · cierre ────────────────────────────────────────────────────────────────────────────────
s = prs.slides.add_slide(BLANCO)
s.background.fill.solid()
s.background.fill.fore_color.rgb = FONDO
texto(s, 1.1, 1.5, 11.3, 2.2, "La aleatoriedad clásica se predice. La recaudación del Perú no debería.", fuente="Georgia", tam=38)
texto(s, 1.1, 3.9, 11.0, 0.9, "Un pipeline que corre de punta a punta en una PC, con un control negativo del pipeline completo y las razones medidas de lo que aún no cumple.", tam=18, color=GRIS)
filete(s, 1.1, 5.4, 11.0, TINTA, 0.01)
texto(s, 1.1, 5.6, 8.0, 0.7, "Gracias. Quedo atento a sus preguntas.", fuente="Georgia", tam=28, color=GRIS)
s.notes_slide.notes_text_frame.text = "Cierre de ocho segundos. Repetir la frase de la tesis y pedir el backend de IBM."

# ── respaldo 1 · preguntas duras ───────────────────────────────────────────────────────────────
s = lamina("Respaldo: preguntas probables del jurado", 11,
           "Respuestas completas en docs/pitch/GUION.md.")
qa = [("¿Dónde está lo cuántico?", "En ningún lado todavía: Aer es pseudoaleatorio. Se valida el postprocesamiento y su medición; el origen depende de la corrida en hardware, que no existe."),
      ("¿Pasa NIST aunque la fuente sea mala?", "Sí, es un hallazgo propio: Peres y Toeplitz bastan para aprobar la batería. Por eso la fuente se mide con 90B y hay un control negativo (E5)."),
      ("M7 falló. ¿Qué hacen?", "El veredicto de E3 se conserva. La reserva de claves (E3b) es otro diseño con su preinscripción; el costo pasa al arranque de 6,6 s."),
      ("¿Por qué una mitigación propia?", "Conserva bits por disparo, que ZNE, PEC y mthree no hacen. No se comparó con TREX sobre hardware: no se sabe cuál corrige mejor la lectura real.")]
for i, (q, a) in enumerate(qa):
    x = 0.9 + (i % 2) * 6.1
    y = 1.95 + (i // 2) * 2.5
    filete(s, x - 0.2, y - 0.1, 5.6)
    texto(s, x, y + 0.1, 5.4, 0.6, q, tam=17, negrita=True)
    texto(s, x, y + 0.75, 5.4, 1.5, a, tam=14, color=GRIS)

# ── respaldo 2 · límites ───────────────────────────────────────────────────────────────────────
s = lamina("Respaldo: lo que este trabajo no afirma", 12,
           "Límites declarados en el informe técnico (docs/paper/paper.pdf).")
lim = ["Origen cuántico: el simulador no aporta entropía cuántica; «certificada» significa «supera esta batería y estas cotas».",
       "Hardware: ninguna corrida en un dispositivo de IBM; TRL del sistema 3.",
       "Poder estadístico: E1, E2 y E5 tienen un poder limitado para fallar (propiedades algebraicas del twirling o control por construcción).",
       "Latencia: E3b se midió en simulador, sin cola ni red de IBM, con una demanda de 100 transacciones por segundo declarada por el equipo.",
       "Dimensionado: el conservador es opcional y no se re-midió en los experimentos de latencia.",
       "Normativa: ninguna norma revisada exige un QRNG; los umbrales de tasa y latencia vienen del equipo."]
texto(s, 0.9, 1.95, 11.5, 4.9, ["■  " + t for t in lim], tam=16, color=GRIS)

prs.save(SALIDA)
print("escrito", SALIDA.name, len(prs.slides._sldIdLst), "láminas")
