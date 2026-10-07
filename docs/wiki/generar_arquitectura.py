"""Mapa 02 — la arquitectura de QRECAUDA: datos · lógica · integración · transversales, tal como la hace cumplir import-linter.

Fuentes únicas: `.importlinter` (contratos), el árbol `src/qrecauda/` (qué módulos existen hoy) y `docs/GLOSARIO.md`.

    python3 docs/wiki/generar_arquitectura.py "docs/wiki/02 — Arquitectura de capas.canvas"
    python3 docs/wiki/publicar.py docs/wiki

Columnas de fuera hacia dentro: transversal ← entrada/api/composición → integración (adaptadores) · presentación →
lógica (aplicación → puertos) → datos → dominio. Una flecha es «puede importar», en su reducción.
"""
from __future__ import annotations

import configparser
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from canvas_lib import Lienzo, informe  # noqa: E402  (vendorizado)

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "qrecauda"

# (id, título, color, rutas relativas a SRC, nota). Color: 6 morado doctrina · 5 cian integración · 4 verde lógica · 3 amarillo transversal · 2 naranja borde
BLOQUES = [
    ("borde", "BORDE · entrada, api, composición", "2", ["entrada", "api.py", "composicion.py"],
     "CLI → fachada → raíz de composición, el ÚNICO sitio que elige adaptadores"),
    ("integracion", "INTEGRACIÓN · adaptadores", "5", ["adaptadores"],
     "uno por puerto; el SDK confinado aquí (C5); no se importan entre sí (C2)"),
    ("presentacion", "PRESENTACIÓN", "2", ["presentacion"], "formatea; no orquesta"),
    ("aplicacion", "LÓGICA · aplicación", "4", ["aplicacion"], "casos de uso y orquestador; sólo puertos y dominio"),
    ("puertos", "PUERTOS", "4", ["puertos"], "Protocol: FuenteDeBits, Mitigador, Validador, Cifrador, Almacen, Reloj, Bitacora"),
    ("datos", "DATOS", "5", ["datos"], "esquema versionado, InformeCorrida, serialización canónica"),
    ("dominio", "LÓGICA · dominio puro", "4", ["dominio"], "sin I/O, reloj, aleatoriedad global ni SDK (C4)"),
    ("transversal", "TRANSVERSALES", "3", ["transversal"], "el núcleo no las importa (C3): le llegan por puertos"),
]


def contratos() -> list[str]:
    cp = configparser.ConfigParser()
    cp.read(RAIZ / ".importlinter", encoding="utf-8")
    return [cp[s]["name"] for s in cp.sections() if s.startswith("importlinter:contract:")]


def modulos(rutas: list[str]) -> list[str]:
    salida: list[str] = []
    for r in rutas:
        base = SRC / r
        if base.is_file():
            salida.append(r.removesuffix(".py"))
        elif base.is_dir():
            salida += [str(p.relative_to(SRC).with_suffix("")) for p in sorted(base.rglob("*.py")) if p.name != "__init__.py"]
    return salida


def lista(mods: list[str]) -> str:
    return "\n".join(f"- `{m}`" for m in mods) if mods else "*(sin módulos con código: sólo el `__init__`)*"


def construir() -> Lienzo:
    nombres = contratos()
    L = Lienzo()
    C = L.columnas("leyenda", "borde", "integracion", "logica", "base", "transversal", desde=-1400)
    L.nodo("leyenda", C["leyenda"], 0, L.ancho, 700, "## QRECAUDA — arquitectura de capas\n"
           "*generado de `.importlinter`, `src/qrecauda/` y `docs/DISENO.md`*\n\n"
           "Una flecha es **«puede importar»**. Cuatro macro-capas: **datos**, **lógica**, **integración** y **transversales**.\n\n"
           f"**Los {len(nombres)} contratos que `lint-imports` hace cumplir:**\n" + "\n".join(f"- {n}" for n in nombres), "6")
    columna = {"borde": "borde", "integracion": "integracion", "presentacion": "integracion", "aplicacion": "logica",
               "puertos": "logica", "datos": "base", "dominio": "base", "transversal": "transversal"}
    pilas: dict[str, object] = {}
    for bid, titulo, color, rutas, nota in BLOQUES:
        col = columna[bid]
        pilas.setdefault(col, L.pila(col, 0))
    grupos: dict[str, list[str]] = {}
    for bid, titulo, color, rutas, nota in BLOQUES:
        pila = pilas[columna[bid]]
        texto = f"### {titulo}\n{nota}\n\n" + lista(modulos(rutas))
        pila.add(bid, max(160, 60 + 28 * texto.count("\n")), texto, color)  # type: ignore[attr-defined]
        grupos.setdefault(columna[bid], []).append(bid)
    for col, etiqueta in (("borde", "ENTRADA"), ("integracion", "INTEGRACIÓN Y PRESENTACIÓN"), ("logica", "LÓGICA (cara externa)"),
                          ("base", "DATOS Y DOMINIO (núcleo)"), ("transversal", "TRANSVERSALES")):
        pilas[col].cerrar(f"g-{col}", etiqueta)  # type: ignore[attr-defined]
    L.arista("g-borde", "g-integracion", label="compone")
    L.arista("g-integracion", "g-logica", label="implementa puertos")
    L.arista("g-logica", "g-base", label="importa")
    L.arista("g-borde", "g-transversal", fs="top", ts="top", label="configura")
    return L


def main(argv: list[str]) -> int:
    out = Path(argv[1]) if len(argv) > 1 else Path(__file__).with_name("02 — Arquitectura de capas.canvas")
    L = construir()
    ok, lineas = informe(L.a_dict(), libres={"leyenda"})
    print("\n".join(lineas))
    if not ok:
        return 1
    L.escribir(out)
    print(f"✓ {out.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
