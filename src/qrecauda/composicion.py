"""Raíz de composición: ÚNICO sitio que elige adaptadores según la configuración.

También es quien aplica lo transversal a una corrida: BLAS a un hilo (`un_hilo`, comprobado con `verificar_un_hilo`) y la captura
del entorno (`entorno`) para la bitácora y el manifiesto. Los SDK pesados se importan al elegir, no al cargar el módulo: el
núcleo corre sin sus extras y un extra ausente se traduce en `FuenteNoDisponible`.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from qrecauda.adaptadores.almacen_json import AlmacenJson
from qrecauda.adaptadores.declaracion_toml import cargar_declaracion
from qrecauda.adaptadores.estadistica import ValidadorEstadistico
from qrecauda.adaptadores.git import HistorialGit
from qrecauda.adaptadores.libro_jsonl import LibroJsonl
from qrecauda.adaptadores.prng import FuentePrng
from qrecauda.aplicacion.juez import CorrerYJuzgar
from qrecauda.aplicacion.pipeline import ParametrosPipeline, Resultado
from qrecauda.aplicacion.pipeline import ejecutar as _ejecutar_pipeline
from qrecauda.aplicacion.transaccion import ServicioDeTransacciones
from qrecauda.datos import Declaracion, InformeCorrida, ManifiestoDeCorrida, Medicion, VeredictoDeEureka
from qrecauda.dominio.errores import EntradaInvalida, FuenteNoDisponible
from qrecauda.puertos import Bitacora, Ejecutor, FuenteDeBits, Historial, Mitigador, Validador
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


# ------------------------------------------------------------------ F2.07: de la declaración a la CLI

_ID_EUREKA = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")
_CLAVES_DE_CONFIGURACION = ("backend", "mitigacion", "nivel_ruido", "validador", "ibm_token_ruta")


class _EjecutorDeInformes:
    """Ejecutor de las eurekas sin criterio propio (E1): una corrida del pipeline REAL por semilla declarada → `InformeCorrida`.

    No corre controles (no inventa lo que no mide): una declaración que los exija se juzga como corrida inválida.
    """

    def __init__(self, historial: Historial) -> None:
        self._historial = historial

    def ejecutar(self, declaracion: Declaracion, semilla: int) -> Medicion:
        cfg = _configuracion_de(declaracion, semilla)
        r = ejecutar(cfg)
        m = r.muestra
        informe = InformeCorrida(
            corrida=declaracion.nodo_corrida, eureka=declaracion.eureka, semilla=semilla, origen=m.origen, procedencia=m.procedencia,
            qubits=cfg.qubits, shots=cfg.shots, mitigada=m.mitigada, epsilon=2.0**-cfg.epsilon_exp,
            profundidad_peres=ParametrosPipeline(cfg.qubits, cfg.shots).profundidad_peres, validador=cfg.validador, estimador="mcv",
            h_min_entrada=r.h_min, h_min_salida=r.h_min_salida, bits_crudos=r.bits_crudos, bits_clave=len(r.clave),
            sha256_muestra_cruda=hashlib.sha256(m.bits.datos.tobytes()).hexdigest(),  # la muestra que entró al extractor
            etapas=dict(r.etapas), veredicto=r.veredicto,
            preinscripcion_sha=self._historial.ultimo_commit(declaracion.rutas), commit=self._historial.commit_actual(),
            entorno=entorno(),
        )  # fmt: skip
        return Medicion(informes=(informe,))


class _SinEjecutor:
    """Para juzgar: el juez sólo relee lo ya medido; si algo intentara correr, es un fallo de uso."""

    def ejecutar(self, declaracion: Declaracion, semilla: int) -> Medicion:
        raise EntradaInvalida("juzgar no corre nada: el ejecutor sólo se usa en `correr`")


def _configuracion_de(decl: Declaracion, semilla: int) -> Configuracion:
    """La Configuracion de UNA semilla: [cadena] (qubits, shots, ε) y las claves de [configuracion] que son de Configuracion."""
    mapa: dict[str, object] = {"qubits": decl.qubits, "shots": decl.shots, "semilla": semilla}
    cadena = decl.tablas.get("cadena", {})
    if "epsilon_log2" in cadena:
        mapa["epsilon_exp"] = -int(cadena["epsilon_log2"])  # type: ignore[call-overload]
    propias = decl.tablas.get("configuracion", {})
    mapa.update({k: propias[k] for k in _CLAVES_DE_CONFIGURACION if k in propias})
    return Configuracion.desde_mapa(mapa)


def ejecutor_de(raiz: Path, decl: Declaracion) -> Ejecutor:
    """E2 y E3 tendrán el suyo con sus nodos de corrida (C.E2, C.E3); hasta entonces se niegan, no se simulan."""
    if decl.eureka in ("E2", "E3"):
        raise FuenteNoDisponible(f"{decl.eureka} aún no tiene ejecutor (nodo {decl.nodo_corrida} del DAG)")
    return _EjecutorDeInformes(HistorialGit(raiz))


def _relativa(ruta: Path, raiz: Path) -> Path:
    if not ruta.is_absolute():
        return ruta
    try:
        return ruta.relative_to(raiz.resolve())
    except ValueError as exc:
        raise EntradaInvalida(f"la declaración {ruta} está fuera de la raíz {raiz}") from exc


def correr_declaracion(ruta: Path, raiz: Path) -> ManifiestoDeCorrida:
    decl = cargar_declaracion(_relativa(Path(ruta), raiz), raiz)
    return juez_de(raiz, ejecutor_de(raiz, decl)).correr(decl)


def juzgar_eureka(eureka: str, raiz: Path) -> VeredictoDeEureka:
    if not _ID_EUREKA.fullmatch(eureka):
        raise EntradaInvalida(f"identificador de eureka {eureka!r} no válido (p. ej. E1)")
    decl = cargar_declaracion(Path("declaraciones") / f"{eureka}.toml", raiz)
    return juez_de(raiz, _SinEjecutor()).juzgar(decl)
