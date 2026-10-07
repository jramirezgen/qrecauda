"""Raíz de composición: ÚNICO sitio que elige adaptadores según la configuración.

También es quien aplica lo transversal a una corrida: BLAS a un hilo (`un_hilo`, comprobado con `verificar_un_hilo`) y la captura
del entorno (`entorno`) para la bitácora y el manifiesto. Los SDK pesados se importan al elegir, no al cargar el módulo: el
núcleo corre sin sus extras y un extra ausente se traduce en `FuenteNoDisponible`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from qrecauda.adaptadores.almacen_json import AlmacenJson
from qrecauda.adaptadores.estadistica import ValidadorEstadistico
from qrecauda.adaptadores.git import HistorialGit
from qrecauda.adaptadores.libro_jsonl import LibroJsonl
from qrecauda.adaptadores.prng import FuentePrng
from qrecauda.aplicacion.juez import CorrerYJuzgar
from qrecauda.aplicacion.pipeline import ParametrosPipeline, Resultado
from qrecauda.aplicacion.pipeline import ejecutar as _ejecutar_pipeline
from qrecauda.aplicacion.transaccion import ServicioDeTransacciones
from qrecauda.dominio.errores import FuenteNoDisponible
from qrecauda.puertos import Bitacora, Ejecutor, FuenteDeBits, Mitigador, Validador
from qrecauda.transversal.configuracion import Configuracion
from qrecauda.transversal.observabilidad import RelojMonotonico
from qrecauda.transversal.reproducibilidad import entorno, un_hilo, verificar_un_hilo


def _modelo_de_ruido(cfg: Configuracion) -> Any:
    try:
        from qrecauda.adaptadores.aer.ruido import NIVELES, modelo_de_ruido, modelo_realista
    except ImportError as e:
        raise FuenteNoDisponible(f"el backend aer_ruidoso necesita el extra «cuantico»: {e}") from e
    return modelo_realista() if cfg.nivel_ruido == "realista" else modelo_de_ruido(NIVELES[cfg.nivel_ruido])


def fuente_de(cfg: Configuracion) -> FuenteDeBits:
    if cfg.backend == "prng":
        return FuentePrng(cfg.semilla)
    if cfg.backend == "aer_ruidoso":
        try:
            from qrecauda.adaptadores.aer import FuenteAer
        except ImportError as e:
            raise FuenteNoDisponible(f"el backend aer_ruidoso necesita el extra «cuantico»: {e}") from e
        return FuenteAer(cfg.semilla, _modelo_de_ruido(cfg))
    raise FuenteNoDisponible(f"el backend {cfg.backend!r} aún no tiene adaptador (DAG F3.04)")


def mitigador_de(cfg: Configuracion) -> Mitigador | None:
    if cfg.mitigacion == "ninguna":
        return None
    try:
        from qrecauda.adaptadores.mthree import TwirlingLectura
    except ImportError as e:
        raise FuenteNoDisponible(f"la mitigación «lectura» necesita el extra «cuantico»: {e}") from e
    return TwirlingLectura(_modelo_de_ruido(cfg), cfg.semilla)


def validador_de(cfg: Configuracion) -> Validador:
    if cfg.validador == "nist":
        try:
            from qrecauda.adaptadores.nist import ValidadorNist
        except ImportError as e:
            raise FuenteNoDisponible(f"el validador nist necesita el extra «validacion»: {e}") from e
        return ValidadorNist()
    return ValidadorEstadistico()


def ejecutar(cfg: Configuracion, bitacora: Bitacora | None = None) -> Resultado:
    """Una corrida completa: BLAS a un hilo (forzado y comprobado) y, si hay bitácora, el entorno y la configuración que la produjeron."""
    p = ParametrosPipeline(cfg.qubits, cfg.shots, epsilon=2.0**-cfg.epsilon_exp)
    with un_hilo():
        verificar_un_hilo()
        if bitacora is not None:
            bitacora.registrar("corrida", configuracion=cfg.como_dict(), entorno=entorno())
        return _ejecutar_pipeline(fuente_de(cfg), validador_de(cfg), RelojMonotonico(), p, mitigador=mitigador_de(cfg))


def servicio_de(cfg: Configuracion, resultado: Resultado) -> ServicioDeTransacciones:
    """El caso de uso del peaje/Metro sobre la clave certificada de `resultado` (AES-256-GCM)."""
    try:
        from qrecauda.adaptadores.aes_gcm import CifradorAesGcm, ReservaDeClave
    except ImportError as e:
        raise FuenteNoDisponible(f"el cifrado necesita el extra «cifrado»: {e}") from e
    return ServicioDeTransacciones(resultado, CifradorAesGcm(), ReservaDeClave)


def juez_de(raiz: Path, ejecutor: Ejecutor) -> CorrerYJuzgar:
    """F2.07: correr y juzgar sobre el repo en `raiz`; escribe en `registro/corridas/` y `registro/veredictos.jsonl`."""
    return CorrerYJuzgar(
        ejecutor,
        AlmacenJson(raiz / "registro" / "corridas"),
        HistorialGit(raiz),
        LibroJsonl(raiz / "registro" / "veredictos.jsonl"),
        entorno(),
    )
