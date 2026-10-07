#!/usr/bin/env python3
"""La identidad y el estado de un artefacto publicado. El «índice» del wiki repo.

Un **wiki repo** es una carpeta `wiki/<PROYECTO>/` de la bóveda declarada como
unidad versionada. El mapeo a git es literal, y es lo que esta biblioteca hace
posible:

| git | wiki repo |
|---|---|
| working tree | la carpeta en la bóveda — **el usuario edita ahí, a mano** |
| índice / HEAD | el manifiesto (`wiki.json`) y los generadores del repo |
| `git status` | `situacion()` sobre cada artefacto |
| `git add` | adoptar: guardar las huellas actuales en el lock |
| `git checkout` | publicar, y **negarse** si pisaría algo no adoptado |

⛔ **Por qué la identidad no son los bytes.** Medido el 2026-09-08 sobre el mismo
canvas: 40 351 bytes en el repo (`json.dumps(indent=1)`) contra **35 926** en la
bóveda (tabuladores, un nodo por línea), md5 distintos… y `json.load` de los dos
**idéntico**. Obsidian reescribe el fichero al abrirlo. Una compuerta que compare
bytes contra la bóveda se dispara cada vez que el usuario abre su propio mapa —
es decir, nace rota y se aprende a ignorar.

⛔ **Por qué el lock guarda CUATRO huellas y no dos.** Con repo vs bóveda sólo se
sabe *que* difieren. Con las dos huellas **adoptadas** —la del repo y la de la
bóveda en el momento de adoptar, igual que el índice de git recuerda el blob y el
árbol— cada lado se compara con **su propio** punto de partida, y sale quién lo
movió, que es lo único accionable:

| ¿se movió el repo? | ¿se movió la bóveda? | situación | ¿se escribe? |
|---|---|---|---|
| — | — | `limpio` si coinciden, `adoptado` si no | **no**, ya está donde toca |
| sí | no | avanzó el **generador** | sí |
| no | sí | lo editó el **usuario** | **no** |
| sí | sí | avanzaron los dos | **no**, decide un humano |

`adoptado` es la fila que hace honesto el sistema: los dos ficheros difieren **a
propósito**, porque alguien lo decidió. Sin ese estado, adoptar una edición manual
la dejaría pisable en la corrida siguiente.

Stdlib pura y sin dependencias de las otras bibliotecas: se vendoriza a cualquier
repo sin coste. No importa `Problema` de `canvas_lib` a propósito — el estado de
un artefacto **no es un defecto**, es dónde está respecto de su manifiesto, y
mezclar los dos conceptos haría que «lo editaste tú» se leyera como un error.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

VERSION = "1.0.0"

#: Procedencias declarables en el manifiesto.
GENERADO = "generado"   # lo produce un script; una edición manual es divergencia
MANUAL = "manual"       # lo escribe el usuario; NUNCA se sobrescribe

#: Situaciones posibles de un artefacto. Vocabulario cerrado.
NUEVO = "nuevo"
LIMPIO = "limpio"
ADOPTADO = "adoptado"
GENERADOR_AVANZO = "generador_avanzo"
EDITADO_A_MANO = "editado_a_mano"
CONFLICTO = "conflicto"
SIN_ADOPTAR = "sin_adoptar"

#: Sólo estas dos situaciones autorizan ESCRIBIR sobre la bóveda, y sólo para un
#: artefacto `generado`. La lista es explícita —y no una negación— para que
#: añadir una situación nueva no autorice a publicar por descuido.
#:
#: `LIMPIO` no está: la bóveda ya tiene ese contenido, y volver a copiarlo sólo
#: cambiaría la serialización (Obsidian escribe con tabuladores, el generador con
#: `indent=1`). Eso ensucia el git del vault sin que nada haya cambiado — y el
#: árbol sucio es justo lo que la compuerta del historial va a mirar.
PUBLICABLES = frozenset({NUEVO, GENERADOR_AVANZO})

#: Situaciones que exigen una DECISIÓN antes de seguir. Todo lo demás (limpio,
#: adoptado) es un estado estable: no se escribe, y tampoco es un fallo.
PROBLEMATICAS = frozenset({EDITADO_A_MANO, CONFLICTO, SIN_ADOPTAR})

EXPLICACION = {
    NUEVO: "todavía no está en la bóveda",
    LIMPIO: "la bóveda tiene exactamente lo que produce el generador",
    ADOPTADO: "difiere del generador, y es la diferencia que adoptaste: no se toca",
    GENERADOR_AVANZO: "el generador produce algo nuevo y la bóveda sigue donde la dejamos",
    EDITADO_A_MANO: "lo cambiaste tú en Obsidian y el lock aún no lo conoce",
    CONFLICTO: "avanzaron el generador Y tu edición: hay que decidir cuál manda",
    SIN_ADOPTAR: "difieren y el lock no guarda huellas: no se puede saber quién fue",
}


@dataclass(frozen=True)
class Artefacto:
    """Lo que `estado` reporta de un artefacto. Sin E/S: se puede probar sin bóveda."""

    nombre: str
    procedencia: str
    situacion: str

    @property
    def publicable(self) -> bool:
        return se_publica(self.procedencia, self.situacion)

    def __str__(self) -> str:
        marca = {LIMPIO: "·", ADOPTADO: "=", NUEVO: "+", GENERADOR_AVANZO: "→",
                 EDITADO_A_MANO: "✎", CONFLICTO: "!", SIN_ADOPTAR: "?"}
        return (f"{marca.get(self.situacion, '?')} {self.nombre}  "
                f"[{self.procedencia}] {self.situacion} — "
                f"{EXPLICACION.get(self.situacion, '')}")


# --------------------------------------------------------------------------
# Huellas
# --------------------------------------------------------------------------

def _sha(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]


def huella_json(texto: str) -> str | None:
    """Identidad **semántica** de un artefacto JSON (`.canvas`).

    Canoniza antes de resumir: claves ordenadas, sin espacios, sin escapar el
    unicode. Así dos serializaciones del mismo contenido dan la misma huella, que
    es justo lo que hace falta cuando Obsidian reescribe el fichero al abrirlo.

    Devuelve `None` si el texto no es JSON: un fichero corrupto **no** puede
    hacerse pasar por válido, y quien llame decide qué hacer con la ausencia.
    """
    try:
        obj = json.loads(texto)
    except (json.JSONDecodeError, ValueError):
        return None
    return _sha(json.dumps(obj, sort_keys=True, ensure_ascii=False,
                           separators=(",", ":")))


def huella_texto(texto: str) -> str:
    """Identidad de un artefacto de texto (`.base`), normalizando sólo el final.

    Aquí NO se canoniza el contenido: un `.base` es YAML y no hay canonicalizador
    en la stdlib. Lo que se normaliza es lo que ningún editor respeta y nadie
    quiso cambiar: los finales de línea y el salto final del fichero.
    """
    return _sha("\n".join(texto.replace("\r\n", "\n").split("\n")).rstrip("\n"))


def huella_de(nombre: str, texto: str) -> str | None:
    return huella_json(texto) if nombre.endswith(".canvas") else huella_texto(texto)


# --------------------------------------------------------------------------
# Estado: quién movió el artefacto
# --------------------------------------------------------------------------

def situacion(en_repo: str | None, en_vault: str | None,
              ad_repo: str | None = None, ad_vault: str | None = None) -> str:
    """Dónde está un artefacto respecto de lo último que se adoptó. Función pura.

    ⛔ **Por qué el lock guarda DOS huellas y no una.** La primera versión sólo
    recordaba la de la bóveda, y eso rompía justo el caso para el que existe todo
    esto: adoptar una edición manual dejaba `bóveda == adoptada`, así que la
    corrida siguiente lo leía como *«avanzó el generador»* y **volvía a pisar la
    edición del usuario**. La compuerta habría protegido el trabajo exactamente
    una vez.

    Con las dos huellas —la del repo y la de la bóveda al adoptar, igual que el
    índice de git recuerda el blob y el árbol— cada lado se compara con **su
    propio** punto de partida, y por eso existe `ADOPTADO`: los dos siguen donde
    los dejamos y simplemente difieren. Esa diferencia es una decisión tomada, no
    un problema pendiente.
    """
    if en_vault is None:
        return NUEVO
    if en_vault == en_repo:
        return LIMPIO
    if ad_repo is None or ad_vault is None:
        return SIN_ADOPTAR
    movio_repo = en_repo != ad_repo
    movio_vault = en_vault != ad_vault
    if movio_repo and movio_vault:
        return CONFLICTO
    if movio_repo:
        return GENERADOR_AVANZO
    if movio_vault:
        return EDITADO_A_MANO
    return ADOPTADO              # ninguno se movió; difieren porque así se quiso


def se_publica(procedencia: str, situacion_actual: str) -> bool:
    """¿Se puede escribir sobre la bóveda sin destruir trabajo de nadie?

    `manual` devuelve `False` **siempre**, incluso estando limpio: el permiso de
    editar a mano no vale nada si el publicador puede pisar el resultado en la
    siguiente corrida. Su artefacto se numera, se le pone ficha y se indexa; su
    contenido no se toca jamás.
    """
    if procedencia != GENERADO:
        return False
    return situacion_actual in PUBLICABLES
