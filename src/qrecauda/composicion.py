"""Raíz de composición: ÚNICO sitio que elige adaptadores según la configuración.

También es quien aplica lo transversal a una corrida: BLAS a un hilo (`un_hilo`, comprobado con `verificar_un_hilo`) y la captura
del entorno (`entorno`) para la bitácora y el manifiesto. Los SDK pesados se importan al elegir, no al cargar el módulo: el
núcleo corre sin sus extras y un extra ausente se traduce en `FuenteNoDisponible`.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from qrecauda.adaptadores.almacen_json import AlmacenJson
from qrecauda.adaptadores.declaracion_toml import cargar_declaracion
from qrecauda.adaptadores.estadistica import ValidadorEstadistico
from qrecauda.adaptadores.git import HistorialGit
from qrecauda.adaptadores.libro_jsonl import LibroJsonl
from qrecauda.adaptadores.prng import FuenteMarkov, FuentePeriodica, FuentePrng
from qrecauda.adaptadores.sonda_local import SondaLocal
from qrecauda.aplicacion.ejecutor_e1 import EjecutorE1
from qrecauda.aplicacion.ejecutor_e2 import EjecutorE2
from qrecauda.aplicacion.ejecutor_e3 import EjecutorE3
from qrecauda.aplicacion.juez import CorrerYJuzgar
from qrecauda.aplicacion.pipeline import ParametrosPipeline, Resultado
from qrecauda.aplicacion.pipeline import ejecutar as _ejecutar_pipeline
from qrecauda.aplicacion.transaccion import ServicioDeTransacciones
from qrecauda.datos import Declaracion, InformeCorrida, ManifiestoDeCorrida, Medicion, RuidoDeLectura, VeredictoDeEureka
from qrecauda.dominio.bits import Bits
from qrecauda.dominio.errores import CorridaInvalida, EntradaInvalida, FuenteNoDisponible
from qrecauda.puertos import (
    Bitacora,
    Ejecutor,
    EstimadorDeEntropia,
    EstimadorDeSesgo,
    FuenteDeBits,
    Historial,
    Mitigador,
    Validador,
)
from qrecauda.transversal.concurrencia import candado
from qrecauda.transversal.configuracion import Configuracion, omp_num_threads
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


# ------------------------------------------------------------------ C.E2 y C.E3: los ejecutores reales


class _LaboratorioAer:
    """Implementa `LaboratorioDeLectura` con Aer, el twirling propio, ZNE/PEC y mthree (los adaptadores, importados al usarlos)."""

    def __init__(self, max_parallel_threads: int | None = None) -> None:
        self._realista: Any = None
        self._hilos = max_parallel_threads  # E3: «un hilo» también en el OpenMP de Aer

    def _modelo(self, ruido: RuidoDeLectura) -> Any:
        try:
            from qrecauda.adaptadores.aer.ruido import CanalLectura, modelo_de_ruido, modelo_realista
        except ImportError as e:
            raise FuenteNoDisponible(f"E2 necesita el extra «cuantico»: {e}") from e
        if ruido.realista:
            if self._realista is None:  # construirlo cuesta; la calibración es congelada, así que es el mismo en toda la corrida
                self._realista = modelo_realista()
            return self._realista
        return None if ruido.canal is None else modelo_de_ruido(CanalLectura(*ruido.canal))

    def fuente(self, ruido: RuidoDeLectura, semilla: int) -> FuenteDeBits:
        try:
            from qrecauda.adaptadores.aer import FuenteAer
        except ImportError as e:
            raise FuenteNoDisponible(f"E2 necesita el extra «cuantico»: {e}") from e
        return FuenteAer(semilla, self._modelo(ruido), self._hilos)

    def twirling(self, ruido: RuidoDeLectura, semilla: int, bloque: int) -> Mitigador:
        try:
            from qrecauda.adaptadores.mthree import TwirlingLectura
        except ImportError as e:
            raise FuenteNoDisponible(f"el twirling necesita el extra «cuantico»: {e}") from e
        return TwirlingLectura(self._modelo(ruido), semilla, bloque, self._hilos)

    def zne(self, ruido: RuidoDeLectura, semilla: int) -> EstimadorDeSesgo:
        from qrecauda.adaptadores.zne_pec import ZneSobreZ

        return ZneSobreZ(self._modelo(ruido), semilla)

    def pec(self, ruido: RuidoDeLectura, semilla: int) -> EstimadorDeSesgo:
        from qrecauda.adaptadores.zne_pec import PecSobreZ

        return PecSobreZ(self._modelo(ruido), None, semilla)  # sin relajación de puerta que invertir: E2 sólo inyecta lectura

    def sesgo_mthree(self, ruido: RuidoDeLectura, qubits: int, shots: int, semilla: int) -> tuple[float, float]:
        from qrecauda.adaptadores.mthree import sesgo_mthree

        return sesgo_mthree(self._modelo(ruido), qubits=qubits, shots=shots, semilla=semilla)


def _alinear_niveles_con_el_toml(decl: Declaracion) -> None:
    """P.E2, «Niveles: discrepancia declarada»: manda PARAMETROS.toml; si la constante del adaptador no coincide, C.E2 ABORTA."""
    try:
        from qrecauda.adaptadores.aer.ruido import NIVELES
    except ImportError as e:
        raise FuenteNoDisponible(f"E2 necesita el extra «cuantico»: {e}") from e
    tabla = decl.tabla("ruido_lectura")
    for nivel in decl.lista("niveles", "sinteticos"):
        canal = NIVELES[nivel]
        declarado = tuple(float(x) for x in tabla[nivel])  # type: ignore[attr-defined]
        if declarado != (canal.p1_dado_0, canal.p0_dado_1):
            raise CorridaInvalida(
                f"el nivel {nivel!r} de PARAMETROS.toml {declarado} no coincide con la constante del adaptador "
                f"{(canal.p1_dado_0, canal.p0_dado_1)}: se alinea antes de correr (P.E2)"
            )


class _EnMaquina:
    """Aplica lo transversal a cada semilla: comprobación previa, candado de máquina y BLAS a un hilo (forzado y comprobado)."""

    def __init__(self, interior: Ejecutor, ruta_candado: Path, previo: Callable[[Declaracion], None], espera_s: float | None) -> None:
        self._interior, self._ruta, self._previo, self._espera = interior, ruta_candado, previo, espera_s

    def ejecutar(self, declaracion: Declaracion, semilla: int) -> Medicion:
        self._previo(declaracion)
        with candado(self._ruta, self._espera), un_hilo():
            verificar_un_hilo()
            return self._interior.ejecutar(declaracion, semilla)


def candado_de_maquina(raiz: Path) -> Path:
    return raiz / "salidas" / "candado_maquina.lock"  # salidas/ está en .gitignore


def ejecutor_e2_de(raiz: Path, bitacora: Bitacora | None = None) -> Ejecutor:
    """C.E2: el ejecutor de E2 sobre Aer, bajo el candado de máquina (espera) y con BLAS a un hilo."""
    return _EnMaquina(EjecutorE2(_LaboratorioAer(), bitacora), candado_de_maquina(raiz), _alinear_niveles_con_el_toml, None)


def _exigir_omp_un_hilo(decl: Declaracion) -> None:
    """P.E3: `OMP_NUM_THREADS=1` ANTES de importar numpy/Aer. Desde dentro ya no se puede arreglar: si no está, se aborta."""
    esperado = str(int(decl.numero("configuracion", "omp_num_threads")))
    if omp_num_threads() != esperado:
        raise CorridaInvalida(
            f"OMP_NUM_THREADS={omp_num_threads()!r}: E3 exige {esperado!r} antes de importar; relanza con OMP_NUM_THREADS={esperado}"
        )


def ejecutor_e3_de(raiz: Path, bitacora: Bitacora | None = None) -> Ejecutor:
    """C.E3: el ejecutor de E3 sobre la cadena REAL (Aer ruidoso + twirling, NIST, 90B, AES-GCM), a un hilo y con candado.

    El candado no espera (`CandadoOcupado` si otra corrida pesada lo tiene): P.E3 pide máquina libre, no una cola."""
    try:
        from qrecauda.adaptadores.aes_gcm import CifradorAesGcm, ReservaDeClave
        from qrecauda.adaptadores.min_entropia import EstimadorNist90B
    except ImportError as e:
        raise FuenteNoDisponible(f"E3 necesita el extra «cifrado»: {e}") from e
    ejecutor = EjecutorE3(
        _LaboratorioAer(max_parallel_threads=1), validador_de(Configuracion(validador="nist")), EstimadorNist90B(),
        CifradorAesGcm, ReservaDeClave, RelojMonotonico(), SondaLocal(), bitacora,
    )  # fmt: skip
    return _EnMaquina(ejecutor, candado_de_maquina(raiz), _exigir_omp_un_hilo, 0.0)


# ------------------------------------------------------------------ C.E1: las cuatro corridas por semilla


def _fuentes_de_control(decl: Declaracion, semilla: int) -> dict[str, FuenteDeBits]:
    """C.E1d: las cuatro fuentes sintéticas con los parámetros de la declaración (como el spike S.04); nada se teclea aquí."""
    d: Mapping[str, Any] = decl.tabla("criterios")["c_e1d"]  # type: ignore[assignment]
    return {
        "sesgada": FuentePrng(semilla, sesgo=float(d["sesgada_p1"]) - 0.5),
        "periodica": FuentePeriodica(str(d["periodica"])),
        "markov": FuenteMarkov(semilla, float(d["markov_permanencia"])),
        "ideal": FuentePrng(semilla),
    }


def _proporciones_nist(bits: Bits, secuencias: int, longitud: int, alfa: float) -> dict[str, dict[str, object]]:
    """SP 800-22 §4.2.1 sobre `secuencias` tramos consecutivos de `longitud` bits, por prueba (M3, M4, M5). Sólo se reporta."""
    try:
        from qrecauda.adaptadores.nist import p_frecuencia_por_bloques, p_monobit, p_runs, proporcion_aprobados
    except ImportError as e:
        raise FuenteNoDisponible(f"la proporción NIST necesita el extra «validacion»: {e}") from e
    salida: dict[str, dict[str, object]] = {}
    for nombre, prueba in (("M3", p_monobit), ("M4", p_runs), ("M5", p_frecuencia_por_bloques)):
        pr = proporcion_aprobados([prueba(bits[i * longitud : (i + 1) * longitud]) for i in range(secuencias)], alfa)
        salida[nombre] = {
            "aprobados": pr.aprobados, "total": pr.total, "proporcion": pr.proporcion,
            "minimo": pr.minimo, "maximo": pr.maximo, "cumple": pr.cumple,
        }  # fmt: skip
    return salida


def _comprobar_e1(decl: Declaracion) -> None:
    """Antes de la primera semilla (que cuesta minutos): el binario del 90B tiene que estar, no descubrirlo tras el Aer."""
    try:
        from qrecauda.adaptadores.min_entropia import BINARIO_POR_DEFECTO, INSTRUCCION_BUILD
    except ImportError as e:  # pragma: no cover - el módulo no importa nada opcional
        raise FuenteNoDisponible(f"E1 necesita el 90B: {e}") from e
    if not BINARIO_POR_DEFECTO.is_file():
        raise FuenteNoDisponible(f"E1 necesita el 90B (C.E1c y C.E1d): falta {BINARIO_POR_DEFECTO}; compílalo con: {INSTRUCCION_BUILD}")


def ejecutor_e1_de(
    raiz: Path,
    bitacora: Bitacora | None = None,
    estimador_90b: EstimadorDeEntropia | None = None,
    historial: Historial | None = None,
) -> Ejecutor:
    """C.E1: las cuatro corridas de E1 por semilla (PRNG, Aer sin mitigar, Aer con twirling, fuentes de control) bajo el candado.

    `estimador_90b` e `historial` sólo se pasan en las pruebas (el 90B real exige ≥ 1 M de bits; `raiz` puede no ser un repo git)."""
    previo = (lambda decl: None) if estimador_90b is not None else _comprobar_e1
    if estimador_90b is None:
        try:
            from qrecauda.adaptadores.min_entropia import EstimadorNist90B
        except ImportError as e:  # pragma: no cover
            raise FuenteNoDisponible(f"E1 necesita el 90B: {e}") from e
        estimador_90b = EstimadorNist90B()
    ejecutor = EjecutorE1(
        _LaboratorioAer(max_parallel_threads=1), FuentePrng, _fuentes_de_control, validador_de(Configuracion(validador="nist")),
        estimador_90b, RelojMonotonico(), historial or HistorialGit(raiz), entorno, _proporciones_nist, bitacora,
    )  # fmt: skip
    return _EnMaquina(ejecutor, candado_de_maquina(raiz), previo, None)


def ejecutor_de(raiz: Path, decl: Declaracion) -> Ejecutor:
    """E1 → C.E1 (cuatro corridas); E2 → C.E2 sobre Aer; E3 → C.E3 sobre la cadena completa; el resto, el pipeline real por semilla."""
    if decl.eureka == "E1":
        return ejecutor_e1_de(raiz)
    if decl.eureka == "E2":
        return ejecutor_e2_de(raiz)
    if decl.eureka == "E3":
        return ejecutor_e3_de(raiz)
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
