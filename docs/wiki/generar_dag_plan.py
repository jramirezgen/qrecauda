# -*- coding: utf-8 -*-
"""Mapa 01 — el DAG del plan de QRECAUDA, coloreado por estado.

Fuente única: `plan/plan.json` + `registro/nodos.jsonl` (vía `plan/dag_lib.py`). Este generador no sabe nada que el plan
no diga. Para que el mapa avance se añade una línea al registro y se publica:

    python3 docs/wiki/generar_dag_plan.py "docs/wiki/01 — El DAG del plan.canvas"
    python3 docs/wiki/publicar.py docs/wiki

Se dibuja la reducción transitiva: una flecha A→C sobra si ya hay A→B→C.
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from canvas_lib import Lienzo, informe   # noqa: E402  (vendorizado)

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "plan"))
import dag_lib as D   # noqa: E402  (fuente única de las reglas)

CONF = D.Config.leer(RAIZ / "plan" / "dag.json")
PLAN = json.loads((RAIZ / "plan" / "plan.json").read_text())
PLAN["nodos"] = D.aplicar_registro(PLAN["nodos"], RAIZ)
NODOS = {n["id"]: n for n in PLAN["nodos"]}
_fallos = D.validar(PLAN["nodos"], RAIZ, CONF)
if _fallos:                                  # un mapa de un plan inválido se seguiría creyendo
    raise SystemExit("✗ el plan no cumple dag_lib, no se dibuja:\n  " + "\n  ".join(_fallos))

# El mapa se dibuja DESDE el tablero (regla 0): cada incidencia anclada con `nodo:` aparece dentro de su nodo.
MANIF = json.loads(Path(__file__).with_name("wiki.json").read_text())
TABLERO = Path(MANIF["vault"]) / "wiki" / MANIF["proyecto"] / MANIF["estructura"]["incidencias"]
INCS = {}
for f in sorted(TABLERO.glob("INC-*.md")):
    fm = f.read_text().split("---")[1]
    campo = lambda k: next((l.split(":", 1)[1].strip() for l in fm.splitlines() if l.startswith(k + ":")), "")  # noqa: E731
    INCS.setdefault(campo("nodo"), []).append(f"[[{f.stem}|{campo('inc')}]] ({campo('situacion')})")

COLOR = {"hecho": "4", "juzgado": "5", "en_curso": "2", "bloqueado": "1", "pausado": "6", "listo": "3", "espera": None}
ICONO = {"hecho": "🟩", "juzgado": "🟦", "en_curso": "🟧", "bloqueado": "🟥", "pausado": "🟪", "listo": "🟨", "espera": "⬜"}
LISTOS = {x["id"] for x in D.listos(list(NODOS.values()))}


def estado_efectivo(n):
    """«listo» lo decide dag_lib.listos, no una segunda copia de la regla."""
    if n["estado"] != "pendiente":
        return n["estado"]
    return "listo" if n["id"] in LISTOS else "espera"


FASES = [("F0", "F0 · FUNDACIÓN — repo, contratos, DAG, hooks, CI"),
         ("F1", "F1 · LÓGICA — dominio puro: Bits, extractores, métricas"),
         ("F2", "F2 · DATOS Y BALA TRAZADORA — puertos, aplicación, almacén, CLI"),
         ("F3", "F3 · INTEGRACIÓN CUÁNTICA — spikes, Aer, ruido, transpilación, IBM"),
         ("F4", "F4 · MITIGACIÓN — lectura, ZNE, PEC"),
         ("F5", "F5 · VALIDACIÓN — NIST y min-entropía"),
         ("F6", "F6 · CASO DE USO — AES-GCM y transacción"),
         ("E", "EUREKAS — preinscripción → corridas → veredicto"),
         ("F7", "F7 · DIFUSIÓN — amenazas, wiki, notebook, pitch, roadmap"),
         ("R", "CIERRE — revisión adversarial y release 0.1.0")]

prof = D.profundidad(list(NODOS.values()))
anc = D.ancestros(list(NODOS.values()))


def aristas_reducidas(i):
    deps = NODOS[i]["depende_de"]
    return [d for d in deps if not any(d in anc[o] for o in deps if o != d)]


L = Lienzo()
C = L.columnas("leyenda", *[f for f, _ in FASES], desde=-1400)
ef = {i: estado_efectivo(n) for i, n in NODOS.items()}
cuenta = Counter(ef.values())
eurekas = [i for i, n in NODOS.items() if n["tipo"] == "eureka"]
eu_hechos = sum(NODOS[i]["estado"] in D.CERRADO for i in eurekas)
siguientes = sorted((i for i in NODOS if ef[i] == "listo"), key=lambda i: (prof[i], i))

L.nodo("leyenda", C["leyenda"], 0, L.ancho, 900, f"""## QRECAUDA — el DAG del plan
*generado de `plan/plan.json` + `registro/` · plan v{PLAN['version_plan']} · {PLAN['fecha']}*

**{len(NODOS)} nodos** · eurekas {eu_hechos}/{len(eurekas)}

{ICONO['hecho']} hecho: **{cuenta['hecho']}** · {ICONO['juzgado']} juzgado: **{cuenta['juzgado']}**
{ICONO['en_curso']} en curso: **{cuenta['en_curso']}**
{ICONO['listo']} listo (dependencias hechas): **{cuenta['listo']}**
{ICONO['espera']} espera dependencias: **{cuenta['espera']}**
{ICONO['bloqueado']} bloqueado: **{cuenta['bloqueado']}**

**Siguiente:** {', '.join(siguientes[:8]) or '—'}

Las flechas son la reducción transitiva de `depende_de`.
⭐ eureka · 🏷️ release · 🧱 insumo (spike) · 🐛 incidencia anclada

**Tablero:** {' · '.join(x for v in INCS.values() for x in v)}""", "6")


def alto(texto):
    lineas = sum(max(1, -(-len(l) // 58)) for l in texto.splitlines())
    return 40 + 27 * lineas


for fase, etiqueta in FASES:
    ids = sorted((i for i, n in NODOS.items() if n["fase"] == fase), key=lambda i: (prof[i], list(NODOS).index(i)))
    p = L.pila(fase, 0)
    for i in ids:
        n = NODOS[i]
        marca = {"eureka": "⭐ ", "release": "🏷️ ", "insumo": "🧱 "}.get(n["tipo"], "")
        txt = (f"### {ICONO[ef[i]]} {marca}{i} · {n['titulo']}\n"
               f"*{n['tipo']}* · **entrega:** {n['entrega']}\n\n"
               f"✔ {n['hecho_cuando']}\n\n"
               f"`cubre:` {', '.join(n['cubre'])}"
               + (f"\n\n*estado:* {n['nota_estado']}" + (f" (`{n['evidencia']}`)" if n.get("evidencia") else "")
                  if n.get("nota_estado") else "")
               + (f"\n\n🐛 {' · '.join(INCS[i])}" if i in INCS else ""))
        p.add(i, alto(txt), txt, COLOR[ef[i]])
    p.cerrar(f"g_{fase}", etiqueta)

for i, n in NODOS.items():
    for d in aristas_reducidas(i):
        misma = NODOS[d]["fase"] == n["fase"]
        L.arista(d, i, *(("bottom", "top") if misma else ("right", "left")), color=COLOR[ef[d]] if ef[d] == "hecho" else None)

out = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).with_name("01 — El DAG del plan.canvas"))
ok, lineas = informe(L.a_dict(), libres={"leyenda"})
for l in lineas:
    print("  " + l)
if not ok:
    raise SystemExit("✗ no se escribe un canvas con etiquetas ilegibles")
L.escribir(out)
print(f"→ {out}  (corredor entre columnas: {L.corredor()} px)")
