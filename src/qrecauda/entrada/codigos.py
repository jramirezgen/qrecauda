"""Tabla estable de códigos de salida: cada excepción con nombre del dominio tiene el suyo."""

from __future__ import annotations

from qrecauda.dominio.errores import (
    AutenticacionFallida,
    EntradaInvalida,
    EntropiaInsuficiente,
    ErrorQRecauda,
    EsquemaFuturo,
    FuenteNoDisponible,
    NonceRepetido,
)

OK = 0
VEREDICTO_RECHAZADO = 1
CODIGOS: dict[type[ErrorQRecauda], int] = {
    EntradaInvalida: 2,
    EntropiaInsuficiente: 3,
    FuenteNoDisponible: 4,
    EsquemaFuturo: 5,
    AutenticacionFallida: 6,
    NonceRepetido: 7,
    ErrorQRecauda: 10,
}


def codigo_de(exc: ErrorQRecauda) -> int:
    for tipo in type(exc).__mro__:
        if tipo in CODIGOS:
            return CODIGOS[tipo]
    return CODIGOS[ErrorQRecauda]
