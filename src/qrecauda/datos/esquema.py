"""Una sola regla de versionado para todos los artefactos: un lector viejo rechaza un esquema futuro."""

from __future__ import annotations

from collections.abc import Mapping

from qrecauda.dominio.errores import EntradaInvalida, EsquemaFuturo


def leer_esquema(d: Mapping[str, object], maximo: int, *, que: str = "artefacto") -> int:
    """Devuelve la versión de esquema de `d`, o aborta si falta, no es entera o es de un futuro que este lector no conoce."""
    if "esquema" not in d:
        raise EntradaInvalida(f"el {que} no declara `esquema`")
    try:
        v = int(str(d["esquema"]))
    except (TypeError, ValueError) as exc:
        raise EntradaInvalida(f"el {que} declara un `esquema` ilegible: {d['esquema']!r}") from exc
    if v > maximo:
        raise EsquemaFuturo(f"{que}: esquema {v} > {maximo}: actualiza qrecauda")
    if v < 1:
        raise EntradaInvalida(f"{que}: esquema {v} inválido")
    return v
