# -*- coding: utf-8 -*-
"""canvas_lib — JSON Canvas 1.0: construccion, layout por columnas y compuerta
de legibilidad.

Por que existe, y de que defecto nace
------------------------------------
El primer canvas de ELEMENT (`element_pipeline_nivelA.canvas`, 65 nodos / 56
aristas) se dibujo con las columnas a **800 px de paso** y nodos de **620 px**
de ancho con **60 px** de padding de grupo. El corredor libre entre dos grupos
contiguos quedaba en `800 - 620 - 2*60 = 60 px`.

Obsidian dibuja la etiqueta de una arista en el **punto medio geometrico** de la
curva — y para una bezier cubica con los tiradores horizontales ese punto medio
es exactamente la media de las dos anclas (los terminos del tirador se cancelan:
`(P0 + 3(P0+d) + 3(P3-d) + P3)/8 = (P0+P3)/2`). Con 60 px de corredor, ese punto
cae **encima del borde de un grupo o dentro del nodo vecino**, y el texto queda
detras. Reportado por el usuario el 2026-09-08: *«el texto que va en el medio no
se ve y se queda atras»*.

La leccion es la de siempre en este entorno: **una regla que no tiene compuerta
no protege nada**. Por eso el layout no se ajusta a ojo — se declara un paso de
columna y `validar()` **mide** si alguna etiqueta quedo tapada o pegada a otra.

Sin dependencias: solo stdlib. Se vendoriza a `docs/wiki/canvas_lib.py` en cada
repo (con su VERSION) para que el repo siga siendo autonomo aunque el disco de
skills no este montado.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

VERSION = "1.1.0"

#: Los seis colores que Obsidian nombra. Cualquier otro valor debe ser un hex.
COLORES = {"1": "rojo", "2": "naranja", "3": "amarillo",
           "4": "verde", "5": "cian", "6": "morado"}

LADOS = ("top", "right", "bottom", "left")

# ── Geometria por defecto ────────────────────────────────────────────────────
# ANCHO + 2*PADDING = 740 px de grupo; PASO 1400 deja **660 px de corredor**,
# once veces el que tenia el primer canvas. Medido: con 660 px ninguna etiqueta
# del pipeline de ELEMENT cae dentro de un nodo.
ANCHO = 620
PADDING_GRUPO = 60
PASO_COLUMNA = 1400
GAP_VERTICAL = 110          # separacion entre nodos apilados en una columna
AIRE_ETIQUETA = 14          # aire minimo entre dos cajas de etiqueta, en px

#: Cuanto tiene que poder CRECER todavia una etiqueta para no avisar, en px.
#:
#: ⛔ La regla dura ("tapada") es un acantilado: medido el 2026-09-08 sobre
#: `apolo_lazo_de_control`, con paso de columna 810 el canvas sale verde y con
#: 800 salen dos etiquetas tapadas. Diez pixeles separan perfecto de roto, y
#: desde dentro del verde no hay forma de saber a que distancia esta el borde.
#: Como el canvas se edita —se le cambia el texto a una arista y la etiqueta
#: crece—, hace falta saberlo ANTES. 100 px son ~13 caracteres a
#: PX_POR_CARACTER: por debajo de eso la etiqueta ya no admite ni una palabra.
MARGEN_ETIQUETA = 100

# Una etiqueta NO es un punto: Obsidian la pinta como una caja de texto centrada
# en el punto medio. Medido sobre la fuente por defecto del canvas: ~7,5 px por
# caracter y ~26 px de alto. Comprobar solo el punto medio es lo que hizo que la
# primera version de esta compuerta diera verde con las 13 etiquetas ilegibles.
PX_POR_CARACTER = 7.5
ALTO_ETIQUETA = 26


@dataclass
class Problema:
    """Un hallazgo del validador. `duro=True` invalida el canvas."""
    regla: str
    detalle: str
    duro: bool = True

    def __str__(self) -> str:
        return f"{'✗' if self.duro else '⚠'} {self.regla}: {self.detalle}"


@dataclass
class Lienzo:
    """Acumula nodos y aristas y los escribe como JSON Canvas 1.0."""
    ancho: int = ANCHO
    padding: int = PADDING_GRUPO
    paso: int = PASO_COLUMNA
    gap: int = GAP_VERTICAL
    nodos: list = field(default_factory=list)
    aristas: list = field(default_factory=list)
    _n_aristas: int = 0
    _columnas: dict = field(default_factory=dict)

    # -- columnas -------------------------------------------------------------
    def columnas(self, *nombres: str, desde: int = 0) -> dict:
        """Declara las columnas de izquierda a derecha y devuelve `{nombre: x}`.

        El paso es uniforme **a proposito**: un corredor de anchura constante es
        lo que hace que las etiquetas quepan sin comprobarlas una a una.
        """
        self._columnas = {n: desde + i * self.paso for i, n in enumerate(nombres)}
        return dict(self._columnas)

    def corredor(self) -> int:
        """Anchura libre entre dos grupos contiguos, en px."""
        return self.paso - self.ancho - 2 * self.padding

    # -- primitivas -----------------------------------------------------------
    def nodo(self, nid, x, y, w, h, text, color=None):
        d = {"id": nid, "type": "text", "x": int(x), "y": int(y),
             "width": int(w), "height": int(h), "text": text}
        if color:
            d["color"] = str(color)
        self.nodos.append(d)
        return d

    def grupo(self, nid, label, x, y, w, h, color=None):
        d = {"id": nid, "type": "group", "x": int(x), "y": int(y),
             "width": int(w), "height": int(h), "label": label}
        if color:
            d["color"] = str(color)
        self.nodos.append(d)
        return d

    def arista(self, a, b, fs="right", ts="left", label=None, color=None):
        self._n_aristas += 1
        d = {"id": f"e{self._n_aristas:03d}", "fromNode": a, "fromSide": fs,
             "toNode": b, "toSide": ts}
        if label:
            d["label"] = label
        if color:
            d["color"] = str(color)
        self.aristas.append(d)
        return d

    # -- apilador -------------------------------------------------------------
    def pila(self, columna: str, y0: int, color=None):
        """Devuelve un apilador vertical para una columna, con su gap declarado."""
        return _Pila(self, self._columnas[columna], y0, color)

    def envolver(self, gid, etiqueta, ids, color=None, cabecera=64, margen=None):
        """Grupo que abarca los nodos dados — sirva o no una sola columna.

        `_Pila.cerrar()` envuelve una columna; esto envuelve una **banda**
        horizontal (varias columnas), que es la forma natural de un lazo de
        control: la cadena directa arriba, el retorno abajo.
        """
        m = self.padding if margen is None else margen
        ns = [n for n in self.nodos if n["id"] in set(ids)]
        if not ns:
            raise ValueError(f"envolver({gid}): ningun nodo de {list(ids)[:3]}…")
        x1 = min(n["x"] for n in ns) - m
        y1 = min(n["y"] for n in ns) - m - cabecera
        x2 = max(n["x"] + n["width"] for n in ns) + m
        y2 = max(n["y"] + n["height"] for n in ns) + m
        return self.grupo(gid, etiqueta, x1, y1, x2 - x1, y2 - y1, color)

    # -- salida ---------------------------------------------------------------
    def a_dict(self) -> dict:
        return {"nodes": self.nodos, "edges": self.aristas}

    def escribir(self, ruta) -> Path:
        ruta = Path(ruta)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(self.a_dict(), ensure_ascii=False, indent=1),
                        encoding="utf-8")
        return ruta


@dataclass
class _Pila:
    """Apila nodos en una columna y cierra el grupo que los envuelve."""
    lienzo: Lienzo
    x: int
    y: int
    color: str | None = None
    _y0: int = 0
    _ids: list = field(default_factory=list)

    def __post_init__(self):
        self._y0 = self.y

    def add(self, nid, alto, text, color=None):
        self.lienzo.nodo(nid, self.x, self.y, self.lienzo.ancho, alto, text,
                         color or self.color)
        self._ids.append(nid)
        self.y += alto + self.lienzo.gap
        return nid

    def cerrar(self, gid, etiqueta, color=None, cabecera=64):
        """Envuelve lo apilado en un grupo. `cabecera` es el hueco del titulo."""
        p = self.lienzo.padding
        alto = (self.y - self.lienzo.gap) - self._y0 + 2 * p + cabecera
        self.lienzo.grupo(gid, etiqueta, self.x - p, self._y0 - p - cabecera,
                          self.lienzo.ancho + 2 * p, alto, color or self.color)
        return gid

    @property
    def ids(self):
        return list(self._ids)


# ── Validacion ───────────────────────────────────────────────────────────────
def _centro(n):
    return n["x"] + n["width"] / 2, n["y"] + n["height"] / 2


def _ancla(n, lado):
    x, y, w, h = n["x"], n["y"], n["width"], n["height"]
    return {"left": (x, y + h / 2), "right": (x + w, y + h / 2),
            "top": (x + w / 2, y), "bottom": (x + w / 2, y + h)}[lado]


def _caja_etiqueta(texto, mx, my):
    """Rectangulo (x1, y1, x2, y2) que ocupa una etiqueta centrada en (mx, my)."""
    w = max(len(texto), 1) * PX_POR_CARACTER
    return mx - w / 2, my - ALTO_ETIQUETA / 2, mx + w / 2, my + ALTO_ETIQUETA / 2


def _margen_etiqueta(caja, mx, textos) -> float:
    """Cuantos px mas de ANCHO admite la etiqueta antes de tocar un nodo.

    La etiqueta crece centrada en `mx`, asi que ganar `d` px de ancho consume
    `d/2` por cada lado: el margen es el doble de la distancia libre al nodo mas
    cercano de su misma franja, menos lo que ya ocupa. Negativo = ya lo toca.
    """
    x1, y1, x2, y2 = caja
    ancho = x2 - x1
    libre = float("inf")
    for t in textos:
        if not (y1 < t["y"] + t["height"] and t["y"] < y2):
            continue                              # no comparten franja vertical
        if t["x"] + t["width"] <= mx:
            libre = min(libre, 2 * (mx - (t["x"] + t["width"])) - ancho)
        elif t["x"] >= mx:
            libre = min(libre, 2 * (t["x"] - mx) - ancho)
        else:
            libre = min(libre, -ancho)            # el punto medio cae DENTRO
    return libre


def _solapan(c, n):
    x1, y1, x2, y2 = c
    return (x1 < n["x"] + n["width"] and n["x"] < x2
            and y1 < n["y"] + n["height"] and n["y"] < y2)


def _dentro(px, py, n, margen=0):
    return (n["x"] - margen <= px <= n["x"] + n["width"] + margen
            and n["y"] - margen <= py <= n["y"] + n["height"] + margen)


def validar(canvas: dict, *, libres=(), aire=AIRE_ETIQUETA,
            margen=MARGEN_ETIQUETA, exigir_grupo=True) -> list:
    """Comprueba el canvas y devuelve los problemas encontrados.

    Reglas duras: ids unicos · extremos de arista resueltos · lados validos ·
    geometria entera y positiva · **ninguna etiqueta de arista tapada por un
    nodo**. Reglas blandas (avisan): **etiqueta sin margen para crecer** ·
    etiquetas demasiado juntas · nodo de texto fuera de todo grupo · nodos
    solapados.

    La dura y la blanda son la misma regla a dos distancias: una etiqueta tapada
    no se publica, y una que ya no cabria si se le añade una palabra se dice. Sin
    la segunda, la compuerta es un acantilado de diez pixeles del que no avisa.
    """
    AVISO = margen
    problemas = []
    nodos = canvas.get("nodes", [])
    aristas = canvas.get("edges", [])
    por_id = {}

    for n in nodos:
        if n["id"] in por_id:
            problemas.append(Problema("id duplicado", n["id"]))
        por_id[n["id"]] = n
        for k in ("x", "y", "width", "height"):
            if not isinstance(n.get(k), int):
                problemas.append(Problema("coordenada no entera",
                                          f"{n['id']}.{k} = {n.get(k)!r}"))
        if n.get("width", 0) <= 0 or n.get("height", 0) <= 0:
            problemas.append(Problema("tamano no positivo", n["id"]))
        if n.get("color") and str(n["color"]) not in COLORES and not str(n["color"]).startswith("#"):
            problemas.append(Problema("color desconocido",
                                      f"{n['id']} = {n['color']!r}", duro=False))

    textos = [n for n in nodos if n.get("type") == "text"]
    grupos = [n for n in nodos if n.get("type") == "group"]

    ids_e = set()
    for e in aristas:
        if e["id"] in ids_e:
            problemas.append(Problema("id de arista duplicado", e["id"]))
        ids_e.add(e["id"])
        for extremo in ("fromNode", "toNode"):
            if e[extremo] not in por_id:
                problemas.append(Problema("arista al vacio",
                                          f"{e['id']}.{extremo} = {e[extremo]}"))
        for lado in ("fromSide", "toSide"):
            if e.get(lado) not in LADOS:
                problemas.append(Problema("lado invalido",
                                          f"{e['id']}.{lado} = {e.get(lado)!r}"))

    # -- la compuerta que este modulo existe para poner --------------------
    etiquetas = []
    for e in aristas:
        if not e.get("label"):
            continue
        a, b = por_id.get(e["fromNode"]), por_id.get(e["toNode"])
        if not a or not b:
            continue
        (x1, y1) = _ancla(a, e.get("fromSide", "right"))
        (x2, y2) = _ancla(b, e.get("toSide", "left"))
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2   # punto medio exacto de la bezier
        caja = _caja_etiqueta(e["label"], mx, my)
        etiquetas.append((e["id"], e["label"], caja))
        tapada = [t["id"] for t in textos if _solapan(caja, t)]
        margen = _margen_etiqueta(caja, mx, textos)
        if not tapada and margen < AVISO:
            problemas.append(Problema(
                "etiqueta sin margen",
                f"{e['id']} «{e['label']}» ({int(caja[2] - caja[0])} px) "
                f"solo puede crecer {int(margen)} px mas antes de tapar un nodo",
                duro=False))
        if tapada:
            problemas.append(Problema(
                "etiqueta tapada",
                f"{e['id']} «{e['label'][:34]}» ({caja[2]-caja[0]:.0f} px) pisa "
                f"{', '.join(tapada)}"))

    # Dos cajas de etiqueta no pueden solaparse (ni rozarse: `aire` de margen).
    # El criterio NO es la distancia entre centros — dos etiquetas en el mismo
    # corredor a 63 px de separacion vertical se leen perfectamente, y un umbral
    # de distancia las marcaba en falso.
    for i in range(len(etiquetas)):
        for j in range(i + 1, len(etiquetas)):
            _, l1, (ax1, ay1, ax2, ay2) = etiquetas[i]
            _, l2, (bx1, by1, bx2, by2) = etiquetas[j]
            if (ax1 - aire < bx2 and bx1 - aire < ax2
                    and ay1 - aire < by2 and by1 - aire < ay2):
                problemas.append(Problema(
                    "etiquetas encimadas",
                    f"«{l1[:28]}» y «{l2[:28]}» se pisan", duro=True))

    if exigir_grupo:
        libres = set(libres)
        for t in textos:
            if t["id"] in libres:
                continue
            cx, cy = _centro(t)
            dentro = [g["id"] for g in grupos if _dentro(cx, cy, g)]
            if len(dentro) != 1:
                problemas.append(Problema(
                    "nodo sin grupo unico",
                    f"{t['id']} esta en {len(dentro)} grupos: {dentro}", duro=False))

    # Dos grupos pueden ANIDARSE (uno dentro de otro) pero nunca solaparse a
    # medias: en Obsidian arrastrar uno se lleva los nodos del otro.
    for i in range(len(grupos)):
        for j in range(i + 1, len(grupos)):
            a, b = grupos[i], grupos[j]
            if not (a["x"] < b["x"] + b["width"] and b["x"] < a["x"] + a["width"]
                    and a["y"] < b["y"] + b["height"] and b["y"] < a["y"] + a["height"]):
                continue
            dentro = lambda u, v: (u["x"] >= v["x"] and u["y"] >= v["y"]
                                   and u["x"] + u["width"] <= v["x"] + v["width"]
                                   and u["y"] + u["height"] <= v["y"] + v["height"])
            if not (dentro(a, b) or dentro(b, a)):
                problemas.append(Problema("grupos solapados a medias",
                                          f"{a['id']} × {b['id']}"))

    for i in range(len(textos)):
        for j in range(i + 1, len(textos)):
            a, b = textos[i], textos[j]
            if (a["x"] < b["x"] + b["width"] and b["x"] < a["x"] + a["width"]
                    and a["y"] < b["y"] + b["height"] and b["y"] < a["y"] + a["height"]):
                problemas.append(Problema("nodos solapados",
                                          f"{a['id']} × {b['id']}", duro=False))

    # ⛔ NO se avisa del nodo que ninguna arista toca. Se intento el 2026-09-09
    # y se retiro el mismo dia, con la medida delante:
    #
    #   * el fallo que la motivo era real ---un nodo nuevo quedo suelto en
    #     `programa.canvas` y el validador lo dio por bueno---;
    #   * pero al pasarla por los nueve repos, aviso de **~150 nodos** que estan
    #     asi a proposito: el diseño dominante de estos canvas es *grupo = pila
    #     de tarjetas, arista = la relacion que si importa*, y ahi el nodo sin
    #     flecha es la norma;
    #   * refinarla a «suelto entre vecinos encadenados» no arreglo nada: casi
    #     todo grupo tiene alguna cadena corta dentro.
    #
    # Una compuerta que grita en la mitad de los casos buenos se aprende a
    # ignorar, y entonces tampoco avisa del caso malo. Volver a intentarlo exige
    # antes que el generador **declare** si su canvas es una cadena o una pila;
    # sin ese dato, la geometria no lo puede adivinar.

    return problemas


def informe(canvas: dict, **kw) -> tuple:
    """Valida y devuelve `(ok, lineas)` listo para imprimir."""
    ps = validar(canvas, **kw)
    duros = [p for p in ps if p.duro]
    n_g = sum(1 for n in canvas["nodes"] if n.get("type") == "group")
    n_t = sum(1 for n in canvas["nodes"] if n.get("type") == "text")
    n_lab = sum(1 for e in canvas["edges"] if e.get("label"))
    lineas = [f"{n_t} nodos de texto · {n_g} grupos · {len(canvas['edges'])} aristas "
              f"({n_lab} con etiqueta)"]
    lineas += [str(p) for p in ps]
    lineas.append("✓ canvas valido" if not duros
                  else f"✗ {len(duros)} problema(s) duro(s)")
    return (not duros), lineas


def main(argv=None):
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(__doc__)
        return 0
    ok_total = True
    for ruta in argv:
        canvas = json.loads(Path(ruta).read_text(encoding="utf-8"))
        ok, lineas = informe(canvas)
        print(f"── {ruta}")
        for l in lineas:
            print("   " + l)
        ok_total &= ok
    return 0 if ok_total else 1


if __name__ == "__main__":
    raise SystemExit(main())
