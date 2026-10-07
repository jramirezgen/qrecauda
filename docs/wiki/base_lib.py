#!/usr/bin/env python3
"""Construye y MIDE una Base de Obsidian (`.base`) antes de escribirla.

Una Base es la base de datos **nativa** de Obsidian (core desde 1.9): un YAML
que filtra notas por su frontmatter y las muestra como tabla o tarjetas. No es
Dataview —que es un plugin de comunidad y ejecuta JS—: aquí no se instala nada,
y el fichero es texto legible que se versiona.

⛔ **Por qué esto valida en vez de sólo emitir.** Obsidian **no avisa** cuando
una base no encuentra nada: dibuja una tabla vacía, que es indistinguible de
«todavía no hay datos». Y una columna que ninguna nota declara sale en blanco
sin decir por qué. Las dos averías son silenciosas, así que se miden antes de
escribir — la misma disciplina que la compuerta de legibilidad de `canvas_lib`.

    from base_lib import Base, Vista, en_carpeta, validar, informe

    b = Base("Ecuaciones", en_carpeta("wiki/ELEMENT/Conceptos/Ecuaciones"),
             [Vista("table", "Por capa", orden=["file.name", "capa", "estado"])])
    ok, lineas = informe(b, Path("/mnt/f/OBSIDIAN"))
    if ok:
        b.escribir(destino)

`Problema` se importa de `canvas_lib` a propósito: «un defecto de un artefacto
del vault tiene regla, detalle y dureza» es **un** concepto, y vive en un solo
sitio. Si algún día hay una tercera biblioteca, se extrae a un `comun.py`; con
dos, extraerlo sería abstraer por si acaso.

Stdlib pura, igual que `canvas_lib`: se vendoriza a cualquier repo sin coste.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from canvas_lib import Problema

VERSION = "1.1.0"

# Vistas que existen en Obsidian, con la versión que las trajo. `table` y
# `cards` son de 1.9 (la versión que estrenó Bases), así que son las únicas que
# se pueden usar sin preguntar por la versión instalada.
TIPOS_DE_VISTA = {"table": "1.9", "cards": "1.9", "list": "1.10",
                  "map": "1.10", "kanban": "1.14"}
TIPOS_SEGUROS = {"table", "cards"}

# Prefijos que NO salen del frontmatter: los da Obsidian.
PREFIJOS_PROPIOS = ("file.", "formula.", "note.")

_RE_FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---", re.DOTALL)
_RE_CLAVE = re.compile(r"^([A-Za-z_][A-Za-z0-9_\-]*)\s*:", re.M)


# --------------------------------------------------------------------------
# Filtros. Se escriben con helpers y no a mano para que un filtro siga siendo
# ANALIZABLE: `validar` necesita saber a qué notas alcanza, y una cadena
# arbitraria no se puede evaluar sin un intérprete de la sintaxis de Obsidian.
# --------------------------------------------------------------------------

def raices_de_boveda(carpeta: Path) -> list[Path]:
    """Las raíces de bóveda que CONTIENEN esta carpeta, medidas en disco.

    Una raíz de bóveda es un directorio con `.obsidian/` dentro: es lo que
    Obsidian abre, y es aquello respecto a lo cual son relativas **todas** las
    rutas de un filtro. Se devuelven de la más profunda a la más superficial.
    La carpeta misma no cuenta: una bóveda cuya raíz es la propia carpeta no
    distingue nada, porque entonces toda nota está dentro.

    ⛔ **Por qué esto se mide y no se supone.** El 2026-09-08 este disco tenía
    dos raíces que contienen `wiki/ELEMENT/`: `/mnt/f/OBSIDIAN` y
    `/mnt/f/OBSIDIAN/wiki` —la segunda es la bóveda anidada de INC-003—, y
    `obsidian.json` decía que la abierta era la segunda. El generador escribió
    la ruta relativa a la primera. Las dos Bases publicadas salieron **vacías**,
    sin un solo aviso: Obsidian dibuja una tabla en blanco, que es lo mismo que
    ve alguien que aún no tiene datos.
    """
    carpeta = Path(carpeta)
    return [p for p in carpeta.parents if (p / ".obsidian").is_dir()]


def en_carpeta(carpeta: Path) -> dict:
    """Notas dentro de una carpeta, dicho una vez por cada raíz de bóveda.

    Toma la ruta **absoluta**, no la relativa: la relativa es justo el dato que
    depende de la raíz, así que pedirla sería pedir la suposición que causó el
    defecto. Con una sola raíz emite un `inFolder` y ya; con varias, un `or`
    que las nombra todas. Que aparezca ese `or` es información y no ruido —
    dice, en el propio artefacto, que en este disco hay más de una bóveda.
    """
    carpeta = Path(carpeta)
    raices = raices_de_boveda(carpeta)
    if not raices:
        raise ValueError(
            f"{carpeta} no está dentro de ninguna bóveda: no hay un `.obsidian/` "
            "ni ahí ni en ninguna carpeta por encima. Un filtro escrito sin raíz "
            "conocida sale vacío y no lo dice.")
    rutas = [f'file.inFolder("{carpeta.relative_to(r).as_posix()}")'
             for r in raices]
    return {"and": [rutas[0] if len(rutas) == 1 else {"or": rutas}]}


def con_etiqueta(tag: str) -> dict:
    return {"and": [f'file.hasTag("{tag}")']}


def y(*filtros: dict) -> dict:
    return {"and": [c for f in filtros for c in f.get("and", [])]}


@dataclass(frozen=True)
class Vista:
    """Una pestaña de la base. `orden` es la secuencia de columnas."""

    tipo: str
    nombre: str
    orden: list[str] = field(default_factory=list)
    limite: int | None = None
    agrupar_por: tuple[str, str] | None = None   # (propiedad, "ASC"|"DESC")
    filtros: dict | None = None


@dataclass
class Base:
    nombre: str
    filtros: dict
    vistas: list[Vista]
    propiedades: dict[str, str] = field(default_factory=dict)   # clave -> rótulo
    formulas: dict[str, str] = field(default_factory=dict)

    # -- emisión ----------------------------------------------------------
    def a_yaml(self) -> str:
        L: list[str] = []
        if self.filtros:
            L.append("filters:")
            L += _yaml_filtros(self.filtros, sangria=1)
        if self.formulas:
            L.append("formulas:")
            L += [f"  {k}: {_escalar(v)}" for k, v in self.formulas.items()]
        if self.propiedades:
            L.append("properties:")
            for clave, rotulo in self.propiedades.items():
                L.append(f"  {clave}:")
                L.append(f"    displayName: {_escalar(rotulo)}")
        L.append("views:")
        for v in self.vistas:
            L.append(f"  - type: {v.tipo}")
            L.append(f"    name: {_escalar(v.nombre)}")
            if v.limite is not None:
                L.append(f"    limit: {v.limite}")
            if v.agrupar_por:
                prop, direccion = v.agrupar_por
                L.append("    groupBy:")
                L.append(f"      property: {prop}")
                L.append(f"      direction: {direccion}")
            if v.filtros:
                L.append("    filters:")
                L += _yaml_filtros(v.filtros, sangria=3)
            if v.orden:
                L.append("    order:")
                L += [f"      - {c}" for c in v.orden]
        return "\n".join(L) + "\n"

    def escribir(self, ruta: str | Path) -> Path:
        p = Path(ruta)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.a_yaml(), encoding="utf-8")
        return p


#: Caracteres que, en primera posición, obligan a entrecomillar en YAML.
_INDICADORES = "-?:,[]{}#&*!|>'\"%@`"

#: Escalares planos que YAML interpretaría como otra cosa.
_RESERVADAS = {"true", "false", "null", "~", "yes", "no", "on", "off"}


def _hace_falta_comilla(v: str) -> bool:
    """¿Este escalar deja de significar lo mismo si va sin comillas?

    ⛔ **El defecto que esto cierra, medido el 2026-09-08.** `_escalar`
    entrecomillaba **siempre**, y Obsidian quita las comillas que YAML no exige
    en cuanto abre la base: 10 escalares cambiaban solos (`displayName: "Capa"`
    → `displayName: Capa`, `- 'estado != "validada"'` → `- estado != "validada"`).
    Resultado: el `.base` del repo y el de la bóveda **nunca** coincidían, así que
    la compuerta que compara los dos nacía roja y sin culpable.

    Se cita sólo lo que YAML obliga a citar. Así el generador habla el mismo
    dialecto que el visor, y una diferencia vuelve a significar algo.
    """
    if v == "" or v != v.strip():
        return True
    if v[0] in _INDICADORES:
        return True
    if v.lower() in _RESERVADAS:
        return True
    if ": " in v or " #" in v or v.endswith(":"):
        return True
    try:                       # un texto que parece número tiene que ir citado
        float(v)
        return True
    except ValueError:
        return False


def _escalar(v: str) -> str:
    return f'"{v}"' if _hace_falta_comilla(v) else v


def _yaml_filtros(nodo: dict | str, sangria: int,
                  *, como_item: bool = False) -> list[str]:
    """Emite un filtro. `como_item` distingue la raíz de un grupo anidado.

    Bajo `filters:` va una clave suelta (`and:`), pero un grupo dentro de otro
    es un elemento de la lista y lleva guion (`- or:`). Sin esa distinción el
    YAML sale con dos claves al mismo nivel y Obsidian se queda con una.
    """
    pad = "  " * sangria
    if isinstance(nodo, str):
        # La doc de Obsidian entrecomilla las comparaciones —`'status != "done"'`—
        # pero el propio Obsidian las reescribe planas en cuanto abre la base
        # (`- estado != "validada"`), y son válidas así: el escalar empieza por
        # letra y las comillas van dentro. Se emite lo que el visor emite, o el
        # fichero cambia solo y la compuerta se queda sin significado.
        return [f"{pad}- {_escalar(nodo)}"]
    L: list[str] = []
    for operador, hijos in nodo.items():
        L.append(f"{pad}{'- ' if como_item else ''}{operador}:")
        for h in hijos:
            L += _yaml_filtros(h, sangria + (2 if como_item else 1),
                               como_item=True)
    return L


# --------------------------------------------------------------------------
# Medición
# --------------------------------------------------------------------------

def _claves_frontmatter(texto: str) -> set[str]:
    m = _RE_FRONTMATTER.search(texto)
    return set(_RE_CLAVE.findall(m.group(1))) if m else set()


def _carpetas_del_filtro(nodo: dict | str) -> list[str]:
    if isinstance(nodo, str):
        m = re.fullmatch(r'file\.inFolder\("(.+)"\)', nodo.strip())
        return [m.group(1)] if m else []
    return [c for hijos in nodo.values() for h in hijos
            for c in _carpetas_del_filtro(h)]


def _etiquetas_del_filtro(nodo: dict | str) -> list[str]:
    if isinstance(nodo, str):
        m = re.fullmatch(r'file\.hasTag\("(.+)"\)', nodo.strip())
        return [m.group(1)] if m else []
    return [t for hijos in nodo.values() for h in hijos
            for t in _etiquetas_del_filtro(h)]


def notas_alcanzadas(base: Base, raiz: Path) -> list[Path]:
    """Las notas que el filtro alcanza, evaluando sólo lo que es analizable.

    Sin carpeta ni etiqueta declaradas devuelve `[]` y la regla de cobertura
    lo dice: **no se adivina** que una base alcanza el vault entero.
    """
    carpetas = _carpetas_del_filtro(base.filtros)
    etiquetas = _etiquetas_del_filtro(base.filtros)
    candidatas: list[Path] = []
    for c in carpetas:
        base_dir = raiz / c
        if base_dir.is_dir():
            candidatas += sorted(base_dir.rglob("*.md"))
    if etiquetas and not carpetas:
        candidatas = sorted((raiz / "wiki").rglob("*.md"))
    if not etiquetas:
        return candidatas
    return [p for p in candidatas if set(etiquetas) & etiquetas_de(p)]


def etiquetas_de(p: Path) -> set[str]:
    """Las etiquetas de una nota, como TOKENS. Pública a propósito.

    La usa también el generador del tablero: si el índice decidiera por su
    cuenta qué nota es una incidencia, tendría un criterio distinto del que
    usa el filtro de la Base — y el 2026-09-08 lo tuvo, así que el índice
    listó unos apuntes sueltos que la tabla no mostraba.

    Comparar por subcadena daba falsos positivos que importan: una nota índice
    con `tags: [indice, ecuaciones]` entraba en un filtro de `ecuacion` —y salía
    en la tabla como una fila vacía, porque un índice no es una ecuación.
    """
    texto = p.read_text(encoding="utf-8", errors="ignore")
    m = _RE_FRONTMATTER.search(texto)
    tags: set[str] = set()
    if m:
        for linea in m.group(1).splitlines():
            if linea.strip().startswith("tags:"):
                crudo = linea.split(":", 1)[1].strip().strip("[]")
                tags |= {t.strip().strip("\"'") for t in crudo.split(",") if t.strip()}
    tags |= set(re.findall(r"(?<!\S)#([A-Za-z0-9_/\-]+)", texto))
    return tags


def raices_alcanzables(base: Base, raiz: Path) -> list[Path]:
    """Las raíces de bóveda desde las que alguien podría abrir esta base.

    Se deducen del propio filtro: se resuelven sus carpetas contra la raíz
    declarada y, de cada una que exista, se miden las bóvedas que la contienen.
    """
    vistas: list[Path] = []
    for c in _carpetas_del_filtro(base.filtros):
        carpeta = raiz / c
        if not carpeta.is_dir():
            continue
        for r in raices_de_boveda(carpeta):
            if r not in vistas:
                vistas.append(r)
    return vistas


def validar(base: Base, raiz: Path) -> list[Problema]:
    """Mide la base contra las notas reales del vault. Duro = no se publica."""
    P: list[Problema] = []

    if not base.vistas:
        P.append(Problema("base sin vista",
                          f"«{base.nombre}» no declara ninguna vista: Obsidian "
                          "la abriría en blanco", True))
    for v in base.vistas:
        if v.tipo not in TIPOS_DE_VISTA:
            P.append(Problema("tipo de vista inexistente",
                              f"«{v.nombre}» pide `{v.tipo}`; Obsidian tiene "
                              f"{sorted(TIPOS_DE_VISTA)}", True))
        elif v.tipo not in TIPOS_SEGUROS:
            P.append(Problema("vista que exige una versión",
                              f"«{v.nombre}» usa `{v.tipo}`, que llegó en "
                              f"Obsidian {TIPOS_DE_VISTA[v.tipo]}", False))

    notas = notas_alcanzadas(base, raiz)
    if not notas:
        P.append(Problema("filtro sin cobertura",
                          f"«{base.nombre}» no alcanza ninguna nota: la tabla "
                          "saldría vacía y eso no se distingue de «aún no hay "
                          "datos»", True))
        return P

    # ⛔ Cobertura desde CADA raíz, no sólo desde la declarada. La regla de
    # arriba mide la intención —«¿existe la carpeta y tiene notas?»— y eso ya
    # se daba por bueno el 2026-09-08 mientras las dos Bases publicadas salían
    # vacías en la bóveda que el usuario abría de verdad. Lo que hay que medir
    # es la cadena emitida, en el sitio donde se ejecuta.
    for r in raices_alcanzables(base, raiz):
        if not notas_alcanzadas(base, r):
            P.append(Problema(
                "filtro atado a una raíz",
                f"«{base.nombre}» no alcanza ninguna nota si la bóveda se abre "
                f"en `{r}`: ahí las rutas del filtro son otras, y la tabla sale "
                "en blanco sin decir por qué", True))

    declaradas = [_claves_frontmatter(p.read_text(encoding="utf-8", errors="ignore"))
                  for p in notas]
    columnas = {c for v in base.vistas for c in v.orden}
    columnas |= {v.agrupar_por[0] for v in base.vistas if v.agrupar_por}
    for c in sorted(columnas):
        if c.startswith(PREFIJOS_PROPIOS):
            continue
        cuantas = sum(1 for d in declaradas if c in d)
        if cuantas == 0:
            P.append(Problema("columna que nadie declara",
                              f"ninguna de las {len(notas)} notas declara "
                              f"`{c}`: saldría una columna en blanco", True))
        elif cuantas < len(notas):
            P.append(Problema("columna incompleta",
                              f"`{c}` la declaran {cuantas} de {len(notas)} "
                              "notas", False))
    return P


def informe(base: Base, raiz: Path) -> tuple[bool, list[str]]:
    P = validar(base, raiz)
    duros = [p for p in P if p.duro]
    lineas = [f"{'✗' if p.duro else '⚠'} {p.regla}: {p.detalle}" for p in P]
    n = len(notas_alcanzadas(base, raiz))
    lineas.append(f"{'✗' if duros else '✓'} «{base.nombre}»: {n} notas "
                  f"alcanzadas, {len(base.vistas)} vista(s), "
                  f"{len(duros)} problema(s) duro(s)")
    return not duros, lineas
