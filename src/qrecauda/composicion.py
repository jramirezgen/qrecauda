"""Raíz de composición: ÚNICO sitio que elige adaptadores según la configuración."""

from __future__ import annotations

from qrecauda.adaptadores.estadistica import ValidadorEstadistico
from qrecauda.adaptadores.prng import FuentePrng
from qrecauda.dominio.errores import FuenteNoDisponible
from qrecauda.puertos import FuenteDeBits, Validador
from qrecauda.transversal.configuracion import Configuracion


def fuente_de(cfg: Configuracion) -> FuenteDeBits:
    if cfg.backend == "prng":
        return FuentePrng(cfg.semilla)
    raise FuenteNoDisponible(f"el backend {cfg.backend!r} aún no tiene adaptador (DAG F3.01/F3.04)")


def validador_de(cfg: Configuracion) -> Validador:
    return ValidadorEstadistico()
