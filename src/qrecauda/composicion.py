"""Raíz de composición: ÚNICO sitio que elige adaptadores según la configuración.

También es quien aplica lo transversal a una corrida: BLAS a un hilo (`un_hilo`, comprobado con `verificar_un_hilo`) y la captura
del entorno (`entorno`) para la bitácora y el manifiesto. Los SDK pesados se importan al elegir, no al cargar el módulo: el
núcleo corre sin sus extras y un extra ausente se traduce en `FuenteNoDisponible`.
"""

from __future__ import annotations

import functools
import hashlib
import re
from collections.abc import Callable, Mapping
from contextlib import ExitStack
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from qrecauda.adaptadores.almacen_json import AlmacenJson
from qrecauda.adaptadores.declaracion_toml import cargar_declaracion
from qrecauda.adaptadores.estadistica import ValidadorEstadistico
from qrecauda.adaptadores.git import HistorialGit
from qrecauda.adaptadores.libro_jsonl import LibroJsonl
from qrecauda.adaptadores.prng import FuenteMarkov, FuentePeriodica, FuentePrng
from qrecauda.adaptadores.sonda_local import SondaLocal
from qrecauda.adaptadores.temporizador_local import TemporizadorLocal
from qrecauda.aplicacion.demo import RamaSolicitada, ResultadoDemo, correr_demo
from qrecauda.aplicacion.dimensionado import estimadores_conservadores
from qrecauda.aplicacion.ejecutor_e1 import EjecutorE1
from qrecauda.aplicacion.ejecutor_e2 import EjecutorE2
from qrecauda.aplicacion.ejecutor_e3 import EjecutorE3
from qrecauda.aplicacion.ejecutor_e3b import EjecutorE3b
from qrecauda.aplicacion.ejecutor_e4 import EjecutorE4, mascaras_de
from qrecauda.aplicacion.ejecutor_e5 import EjecutorE5
from qrecauda.aplicacion.juez import CorrerYJuzgar
from qrecauda.aplicacion.pipeline import ParametrosPipeline, Resultado
from qrecauda.aplicacion.pipeline import ejecutar as _ejecutar_pipeline
from qrecauda.aplicacion.reserva_asincrona import PASO_SEMILLA, PASO_SEMILLA_HEREDADO, GeneradorDeClaveAprobada
from qrecauda.aplicacion.transaccion import ServicioDeTransacciones
from qrecauda.datos import Declaracion, InformeCorrida, ManifiestoDeCorrida, Medicion, RuidoDeLectura, VeredictoDeEureka
from qrecauda.dominio.bits import Bits
from qrecauda.dominio.errores import CorridaInvalida, EntradaInvalida, FuenteNoDisponible, PresupuestoQpuExcedido
from qrecauda.dominio.muestra import Muestra
from qrecauda.dominio.presupuesto_qpu import TOPE_POR_OMISION_S, validar_tope_qpu
from qrecauda.puertos import (
    Bitacora,
    Ejecutor,
    EstimadorDeEntropia,
    EstimadorDeSesgo,
    FuenteDeBits,
    FuenteDeContraste,
    GeneradorDeClaves,
    Historial,
    Mitigador,
    ProductorDeClaves,
    Validador,
)
from qrecauda.transversal.concurrencia import candado
from qrecauda.transversal.configuracion import Configuracion, omp_num_threads
from qrecauda.transversal.observabilidad import RelojMonotonico
from qrecauda.transversal.reproducibilidad import (
    afinidad,
    entorno,
    fijar_afinidad,
    nucleo_fijo,
    un_hilo,
    un_hilo_en_este_proceso,
    verificar_un_hilo,
)


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
    if cfg.backend == "ibm":
        fuente: FuenteDeBits = fuente_ibm_de(cfg, instancia=cfg.ibm_instancia)  # el tope por omisión lo pone `fuente_ibm_de`
        return fuente
    raise FuenteNoDisponible(f"el backend {cfg.backend!r} no tiene adaptador")


def fuente_ibm_de(
    cfg: Configuracion,
    conectar: Callable[[Any], Any] | None = None,
    fabricas: Any = None,
    *,
    ensayo: bool = False,
    mascaras: int = 0,
    max_segundos_qpu: float | None = None,
    ia: bool = False,
    espera_max_s: float | None = None,
    instancia: str = "",
) -> Any:
    """F3.04/F3.07: SamplerV2 sobre IBM. La ruta del token se lee aquí (falta ⇒ `FuenteNoDisponible`); la red se toca en `generar`.

    La transpilación a forma ISA (F3.03) se inyecta desde aquí: el adaptador de IBM no importa el de Aer (C2). `ia=True` pide el
    enrutado con IA y, si falta `qiskit_ibm_transpiler`, DEGRADA con aviso. `ensayo=True` recorre todo el camino contra un backend
    falso de IBM, sin token ni cuota. `conectar` y `fabricas` sólo se pasan en las pruebas (dobles sin red).

    Sin `max_segundos_qpu` rige `TOPE_POR_OMISION_S`: ninguna ruta, ni `qrecauda` sin subcomando, envía a hardware sin tope (R.02)."""
    try:
        from qrecauda.adaptadores.aer.transpilacion import a_isa
        from qrecauda.adaptadores.ibm_runtime import FuenteIbm, conectar_real
    except ImportError as e:
        raise FuenteNoDisponible(f"el backend ibm necesita el extra «cuantico»: {e}") from e

    def transpilar(circuito: Any, backend: Any) -> Any:
        return a_isa(circuito, backend, semilla=cfg.semilla, ia=ia)

    comunes: dict[str, Any] = {
        "transpilar": transpilar,
        "mascaras": mascaras,
        "semilla": cfg.semilla,
        "max_segundos_qpu": validar_tope_qpu(TOPE_POR_OMISION_S if max_segundos_qpu is None else max_segundos_qpu),
        "espera_max_s": espera_max_s,
    }
    if ensayo:
        return FuenteIbm.para_ensayo(backend=cfg.ibm_backend or "fake_sherbrooke", **comunes)
    return FuenteIbm.desde_ruta(
        Path(cfg.ibm_token_ruta),
        backend=cfg.ibm_backend,
        modo=cfg.ibm_modo,
        conectar=conectar or conectar_real,
        fabricas=fabricas,
        instancia=instancia or cfg.ibm_instancia,
        **comunes,
    )


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
_CLAVES_DE_CONFIGURACION = ("backend", "mitigacion", "nivel_ruido", "validador", "ibm_token_ruta", "ibm_backend", "ibm_modo")


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

    def __init__(
        self,
        interior: Ejecutor,
        ruta_candado: Path,
        previo: Callable[[Declaracion], None],
        espera_s: float | None,
        nucleo: Callable[[Declaracion], int] | None = None,
    ) -> None:
        self._interior, self._ruta, self._previo, self._espera, self._nucleo = interior, ruta_candado, previo, espera_s, nucleo

    def ejecutar(self, declaracion: Declaracion, semilla: int) -> Medicion:
        self._previo(declaracion)
        with ExitStack() as pila:
            pila.enter_context(candado(self._ruta, self._espera))
            if self._nucleo is not None:  # E3b: el proceso del consumidor (y los que cree, que lo heredan) en SU núcleo
                pila.enter_context(nucleo_fijo(self._nucleo(declaracion)))
            pila.enter_context(un_hilo())
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


# ------------------------------------------------------------------ C.E3b: la reserva de claves en un proceso aparte


@dataclass(frozen=True, slots=True)
class _EspecificacionDeProductor:
    """Todo lo que el proceso productor necesita para armar su cadena; sólo datos simples, para que cruce a un proceso `spawn`."""

    semilla: int
    nucleo: int
    nivel: str
    canal: tuple[float, float]
    qubits: int
    shots: int
    epsilon_exp: int
    profundidad_peres: int
    bloque_twirling: int
    muestras_90b: int
    permitidos: tuple[int, ...]  # los núcleos de la máquina ANTES de fijar al consumidor: el hijo hereda esa fijación
    paso_semilla: int  # factor de «semilla · paso + i», sacado de la regla que DECLARA la declaración (C.E3b se midió con 100)


_PASO_DE_REGLA = {"semilla * 100 + i": PASO_SEMILLA_HEREDADO, f"semilla * {PASO_SEMILLA} + i": PASO_SEMILLA}


def _especificacion_de(decl: Declaracion, semilla: int, permitidos: tuple[int, ...]) -> _EspecificacionDeProductor:
    regla = str(decl.tabla("configuracion")["semilla_clave"])
    if regla not in _PASO_DE_REGLA:
        raise EntradaInvalida(f"[configuracion].semilla_clave {regla!r} fuera de {sorted(_PASO_DE_REGLA)}")
    nivel = str(decl.tabla("configuracion")["nivel_ruido"])
    par = decl.tabla("ruido_lectura")[nivel]
    return _EspecificacionDeProductor(
        semilla, int(decl.numero("configuracion", "nucleo_productor")), nivel, (float(par[0]), float(par[1])),  # type: ignore[index]
        decl.qubits, decl.shots, int(decl.numero("cadena", "epsilon_log2")), int(decl.numero("cadena", "profundidad_peres")),
        int(decl.numero("configuracion", "twirling_bloque")), int(decl.numero("validacion", "muestras_90b")), permitidos,
        _PASO_DE_REGLA[regla],
    )  # fmt: skip


def _generador_en_hijo(esp: _EspecificacionDeProductor) -> GeneradorDeClaves:
    """Corre DENTRO del proceso productor, antes de la primera clave: su núcleo, su único hilo y los adaptadores reales de E3."""
    fijar_afinidad(esp.nucleo, esp.permitidos)
    un_hilo_en_este_proceso()
    if omp_num_threads() != "1":
        raise CorridaInvalida(f"el productor hereda OMP_NUM_THREADS={omp_num_threads()!r}; E3b exige '1' antes de importar")
    verificar_un_hilo()
    try:
        from qrecauda.adaptadores.min_entropia import EstimadorNist90B
    except ImportError as e:
        raise FuenteNoDisponible(f"E3b necesita el 90B y el extra «validacion»: {e}") from e
    parametros = ParametrosPipeline(esp.qubits, esp.shots, epsilon=2.0**esp.epsilon_exp, profundidad_peres=esp.profundidad_peres)
    return GeneradorDeClaveAprobada(
        _LaboratorioAer(max_parallel_threads=1),
        validador_de(Configuracion(validador="nist")),
        EstimadorNist90B(),
        RelojMonotonico(),
        RuidoDeLectura(esp.nivel, esp.canal),
        parametros,
        esp.bloque_twirling,
        esp.muestras_90b,
        esp.semilla,
        paso_semilla=esp.paso_semilla,
    )


def _comprobar_e3b(decl: Declaracion) -> None:
    """Antes de la primera semilla: OMP a 1, núcleos declarados distintos y permitidos, y el binario del 90B."""
    _exigir_omp_un_hilo(decl)
    consumidor, productor = int(decl.numero("configuracion", "nucleo_consumidor")), int(decl.numero("configuracion", "nucleo_productor"))
    if consumidor == productor:
        raise CorridaInvalida(f"E3b exige dos núcleos distintos; la declaración fija el {consumidor} para los dos")
    ajenos = sorted({consumidor, productor} - set(afinidad()))
    if ajenos:
        raise CorridaInvalida(f"los núcleos declarados {ajenos} no están entre los permitidos de este proceso {list(afinidad())}")
    try:
        from qrecauda.adaptadores.min_entropia import BINARIO_POR_DEFECTO, INSTRUCCION_BUILD
    except ImportError as e:  # pragma: no cover - el módulo no importa nada opcional
        raise FuenteNoDisponible(f"E3b necesita el 90B: {e}") from e
    if not BINARIO_POR_DEFECTO.is_file():
        raise FuenteNoDisponible(f"E3b necesita el 90B: falta {BINARIO_POR_DEFECTO}; compílalo con: {INSTRUCCION_BUILD}")


def ejecutor_e3b_de(raiz: Path, bitacora: Bitacora | None = None) -> Ejecutor:
    """C.E3b: la reserva de claves en un proceso productor aparte (spawn, su núcleo, un hilo) y el consumidor en el suyo, bajo el candado.

    El candado no espera (`CandadoOcupado`): P.E3b pide máquina libre, no una cola."""
    try:
        from qrecauda.adaptadores.aes_gcm import CifradorAesGcm, ReservaDeClave
        from qrecauda.adaptadores.productor_en_proceso import ProductorEnProceso
    except ImportError as e:
        raise FuenteNoDisponible(f"E3b necesita el extra «cifrado»: {e}") from e

    permitidos = afinidad()  # antes de que el consumidor se fije a su núcleo

    def productor(decl: Declaracion, semilla: int) -> ProductorDeClaves:
        fabrica = functools.partial(_generador_en_hijo, _especificacion_de(decl, semilla, permitidos))
        return ProductorEnProceso(fabrica, int(decl.numero("reserva", "capacidad_claves")))

    ejecutor = EjecutorE3b(
        productor, CifradorAesGcm, ReservaDeClave, RelojMonotonico(), TemporizadorLocal(), SondaLocal(), bitacora, afinidad
    )
    return _EnMaquina(
        ejecutor, candado_de_maquina(raiz), _comprobar_e3b, 0.0, nucleo=lambda decl: int(decl.numero("configuracion", "nucleo_consumidor"))
    )


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


# ------------------------------------------------------------------ C.E5: el control negativo de la cadena completa


def _defecto_de(decl: Declaracion, nombre: str, semilla: int) -> Callable[[Bits], Bits]:
    """El defecto declarado en [defectos.<nombre>], con la semilla del defecto = semilla + desplazamiento (independiente de la de Aer)."""
    from qrecauda.adaptadores.defectos import patron, persistencia

    d = decl.tabla("defectos").get(nombre)
    if not isinstance(d, dict):
        raise EntradaInvalida(f"E5: la fuente {nombre!r} no tiene [defectos.{nombre}]")
    s = semilla + int(decl.numero("defectos", "desplazamiento_semilla"))
    if d["tipo"] == "persistencia":
        return persistencia(float(d["peso"]), s)
    if d["tipo"] == "patron":
        return patron(float(d["peso"]), str(d["patron"]), s)
    raise EntradaInvalida(f"E5: tipo de defecto desconocido {d['tipo']!r} en [defectos.{nombre}]")


def _fabrica_e5(laboratorio: _LaboratorioAer) -> Callable[[Declaracion, str, int], tuple[FuenteDeBits, Mitigador]]:
    def fabrica(decl: Declaracion, nombre: str, semilla: int) -> tuple[FuenteDeBits, Mitigador]:
        nivel = str(decl.tabla("ruido")["nivel"])
        par = decl.tabla("ruido_lectura").get(nivel)
        if not isinstance(par, list) or len(par) != 2:
            raise EntradaInvalida(f"el nivel {nivel!r} de [ruido] no está en [ruido_lectura] de PARAMETROS.toml")
        ruido = RuidoDeLectura(nivel, (float(par[0]), float(par[1])))
        fuente = laboratorio.fuente(ruido, semilla)
        mitigador = laboratorio.twirling(ruido, semilla, int(decl.numero("ruido", "twirling_bloque")))
        if nombre == "buena":
            return fuente, mitigador
        from qrecauda.adaptadores.defectos import MitigadorConDefecto

        return fuente, MitigadorConDefecto(mitigador, _defecto_de(decl, nombre, semilla))

    return fabrica


def ejecutor_e5_de(raiz: Path, bitacora: Bitacora | None = None, estimador_90b: EstimadorDeEntropia | None = None) -> Ejecutor:
    """C.E5: cada fuente (buena y tres con defecto) por los tres dimensionados, la cadena REAL de punta a punta, bajo el candado.

    `estimador_90b` sólo se pasa en las pruebas (el 90B real exige ≥ 1 M de bits)."""
    previo = (lambda decl: None) if estimador_90b is not None else _comprobar_e1
    if estimador_90b is None:
        try:
            from qrecauda.adaptadores.min_entropia import EstimadorNist90B
        except ImportError as e:  # pragma: no cover
            raise FuenteNoDisponible(f"E5 necesita el 90B: {e}") from e
        estimador_90b = EstimadorNist90B()
    ejecutor = EjecutorE5(
        _fabrica_e5(_LaboratorioAer(max_parallel_threads=1)), validador_de(Configuracion(validador="nist")),
        estimador_90b, RelojMonotonico(), SondaLocal(), bitacora,
    )  # fmt: skip
    return _EnMaquina(ejecutor, candado_de_maquina(raiz), previo, None)


# ------------------------------------------------------------------ C.E4 y la demo: el contraste con hardware


class _VistaDeContraste:
    """Una de las dos caras de un contraste: devuelve la muestra ya medida, sin volver a enviar nada."""

    def __init__(self, obtener: Callable[[], Muestra]) -> None:
        self._obtener = obtener

    def generar(self, qubits: int, shots: int) -> Muestra:
        m = self._obtener()
        if (m.qubits, m.shots) != (qubits, shots):
            raise EntradaInvalida(f"el contraste midió {m.qubits}×{m.shots}, no {qubits}×{shots}: las dos caras salen del mismo envío")
        return m


class ContrasteIbm:
    """Implementa `FuenteDeContraste` sobre `FuenteIbm`: UN envío, dos caras (cruda y twirling). `cruda()` envía; `con_twirling()` no.

    Es ansiosa a propósito: el trabajo (cola incluida) ocurre al pedir la primera cara, FUERA de cualquier reloj de cadena."""

    def __init__(self, ibm: Any, qubits: int, shots: int) -> None:
        self._ibm, self._qubits, self._shots = ibm, qubits, shots
        self._caras: tuple[Muestra, Muestra] | None = None
        self._gemelos: tuple[Muestra, Muestra] | None = None

    def _enviar(self) -> tuple[Muestra, Muestra]:
        if self._caras is None:
            self._caras = self._ibm.generar_contraste(self._qubits, self._shots)
        return self._caras

    def cruda(self) -> FuenteDeBits:
        cruda = self._enviar()[0]
        return _VistaDeContraste(lambda: cruda)

    def con_twirling(self) -> FuenteDeBits:
        twirl = self._enviar()[1]
        return _VistaDeContraste(lambda: twirl)

    def _gemelo(self) -> tuple[Muestra, Muestra]:
        if self._gemelos is None:
            self._enviar()  # primero el hardware: si el envío aborta (presupuesto, cola), no se gasta tiempo en simular
            self._gemelos = self._ibm.generar_gemelo(self._qubits, self._shots)
        return self._gemelos

    def gemelo_cruda(self) -> FuenteDeBits:
        cruda = self._gemelo()[0]
        return _VistaDeContraste(lambda: cruda)

    def gemelo_con_twirling(self) -> FuenteDeBits:
        twirl = self._gemelo()[1]
        return _VistaDeContraste(lambda: twirl)

    def registro(self) -> Mapping[str, object]:
        self._enviar()
        r = self._ibm.ultimo_registro
        if r is None:
            raise CorridaInvalida("el envío a IBM no dejó registro del trabajo: sin job_id no hay hardware que reclamar")
        return dict(r.a_mapa())


class _EnUnHilo:
    """BLAS a un hilo (forzado y comprobado) SIN candado de máquina: E4 espera la cola de IBM y no puede retener la máquina horas.
    M6/M7 de E4 son informativas (P.E4), así que no necesitan la máquina en exclusiva."""

    def __init__(self, interior: Ejecutor) -> None:
        self._interior = interior

    def ejecutar(self, declaracion: Declaracion, semilla: int) -> Medicion:
        with un_hilo():
            verificar_un_hilo()
            return self._interior.ejecutar(declaracion, semilla)


def ejecutor_e4_de(
    raiz: Path,
    *,
    token_ruta: str = "",
    backend: str = "",
    ensayo: bool = False,
    max_segundos_qpu: float | None = None,
    ia: bool = False,
    instancia: str = "",
    bitacora: Bitacora | None = None,
    historial: Historial | None = None,
    contraste: Callable[[Declaracion, int], FuenteDeContraste] | None = None,
    conectar: Callable[[Any], Any] | None = None,
    fabricas: Any = None,
) -> Ejecutor:
    """C.E4: las cinco corridas de E4 por semilla (PRNG, Aer realista cruda y con twirling, hardware crudo y con twirling).

    `contraste`, `conectar` y `fabricas` sólo se pasan en las pruebas. Sin token ni `ensayo` no se envía nada: `FuenteNoDisponible`."""
    if contraste is None:
        if not ensayo and not token_ruta:
            raise FuenteNoDisponible("E4 necesita la credencial de IBM (--token-file RUTA) o --ensayo: sin credencial IBM no hay hardware")

        usados: list[Any] = []  # las FuenteIbm de las semillas ya enviadas: el tope es de TODA la corrida, no de cada trabajo

        def contraste(decl: Declaracion, semilla: int) -> FuenteDeContraste:
            por_omision = decl.tablas.get("hardware", {}).get("tope_qpu_por_omision_s")
            tope = (
                max_segundos_qpu
                if max_segundos_qpu is not None
                else float(por_omision)
                if isinstance(por_omision, int | float)
                else TOPE_POR_OMISION_S
            )
            restante = tope - sum(f.gastado_estimado_s for f in usados)
            if restante <= 0:
                raise PresupuestoQpuExcedido(
                    f"el tope de {tope:.1f} s de QPU de la corrida ya está gastado: no se envía el trabajo de {semilla}"
                )
            cfg = Configuracion(
                backend="ibm" if not ensayo else "prng", semilla=semilla, ibm_token_ruta=token_ruta, ibm_backend=backend,
                ibm_modo="trabajo", ibm_instancia=instancia,
            )  # fmt: skip
            espera = decl.tablas.get("hardware", {}).get("espera_max_s")
            ibm = fuente_ibm_de(
                cfg, conectar, fabricas, ensayo=ensayo, mascaras=mascaras_de(decl), max_segundos_qpu=restante, ia=ia,
                espera_max_s=float(espera) if isinstance(espera, int | float) else None,
            )  # fmt: skip
            if not usados:  # antes de enviar el primero: ¿caben TODOS los trabajos? Una corrida a medias gasta cuota y deja artefactos
                ibm.exigir_presupuesto_de(decl.qubits, decl.shots, len(decl.semillas))
            usados.append(ibm)
            return ContrasteIbm(ibm, decl.qubits, decl.shots)

    ejecutor = EjecutorE4(
        FuentePrng, contraste, validador_de(Configuracion(validador="nist")), RelojMonotonico(), historial or HistorialGit(raiz), entorno,
        bitacora,
    )  # fmt: skip
    return _EnUnHilo(ejecutor)


def correr_hardware(
    raiz: Path,
    declaracion: Path = Path("declaraciones/E4.toml"),
    *,
    token_ruta: str = "",
    backend: str = "",
    ensayo: bool = False,
    max_segundos_qpu: float | None = None,
    ia: bool = False,
    instancia: str = "",
    historial: Historial | None = None,
    contraste: Callable[[Declaracion, int], FuenteDeContraste] | None = None,
) -> ManifiestoDeCorrida:
    """F3.07: el contraste de E4. Real ⇒ `registro/corridas/` (la preinscripción tiene que estar commiteada). `ensayo` ⇒ todo el
    camino contra un backend falso de IBM, SIN cuota ni credencial, y escribe en `salidas/ensayo_e4/` (nunca en el registro)."""
    if max_segundos_qpu is not None:
        validar_tope_qpu(max_segundos_qpu)  # nan/inf/1e12 abortan aquí, antes de cargar nada y con un error claro
    decl = cargar_declaracion(_relativa(Path(declaracion), raiz), raiz)
    if decl.eureka != "E4":
        raise EntradaInvalida(f"`hardware` corre E4, no {decl.eureka}")
    ejecutor = ejecutor_e4_de(
        raiz, token_ruta=token_ruta, backend=backend, ensayo=ensayo, max_segundos_qpu=max_segundos_qpu, ia=ia, instancia=instancia,
        historial=historial, contraste=contraste,
    )  # fmt: skip
    if not ensayo:
        return juez_de(raiz, ejecutor).correr(decl)
    carpeta = raiz / "salidas" / "ensayo_e4"
    juez = CorrerYJuzgar(
        ejecutor, AlmacenJson(carpeta), historial or HistorialGit(raiz), LibroJsonl(carpeta / "veredictos.jsonl"), entorno()
    )
    return juez.correr(decl)


DEMO_QUBITS = 8
DEMO_SHOTS_AER = {False: 100_000, True: 40_000}  # por `rapido`
DEMO_SHOTS_IBM = {False: 40_000, True: 16_000}  # divisibles por 8 PUBs; pocos: la demo no debe gastar la cuota
DEMO_MASCARAS_IBM = 7
DEMO_BLOQUE = 1000


def demo_de(
    cfg: Configuracion,
    *,
    rapido: bool = False,
    fuente: str = "aer",
    ensayo: bool = False,
    max_segundos_qpu: float | None = None,
    shots: int | None = None,
    conectar: Callable[[Any], Any] | None = None,
    fabricas: Any = None,
    estimador_90b: EstimadorDeEntropia | None = None,
) -> ResultadoDemo:
    """F7.07: PRNG, Aer sin mitigar y Aer con twirling lado a lado y, con `fuente="ibm"`, también el hardware (o su ensayo).

    `cfg.dimensionado` elige «mcv» (0.1.0, por omisión) o «conservador» (F5.05: mínimo(MCV, 90B) + contabilidad de la fuente, como E5).
    `estimador_90b` sólo se pasa en las pruebas (el 90B real exige >= 1 Mbit por rama y el binario compilado)."""
    if max_segundos_qpu is not None:
        validar_tope_qpu(max_segundos_qpu)
    if shots is not None and shots < 1:
        raise EntradaInvalida(f"--shots debe ser positivo, llegó {shots}")
    if fuente not in ("aer", "ibm"):
        raise EntradaInvalida(f"fuente {fuente!r} fuera de ('aer', 'ibm')")
    if ensayo and fuente != "ibm":
        raise EntradaInvalida("--ensayo ensaya el camino a IBM: úsalo con --fuente ibm")
    if fuente == "ibm" and not ensayo and not cfg.ibm_token_ruta:
        raise FuenteNoDisponible("--fuente ibm exige --token-file RUTA (o QRECAUDA_IBM_TOKEN_FILE); con --ensayo no hace falta")
    avisos: list[str] = []
    try:
        validador = validador_de(Configuracion(validador="nist"))
    except FuenteNoDisponible as e:
        validador = validador_de(Configuracion())
        avisos.append(f"batería NIST no disponible, se usa el validador estadístico: {e}")
    ruido = Configuracion(nivel_ruido="medio")  # el de E1: sesgo analítico 0,03; el realista (127 qubits) tarda ~1 s por bloque
    try:
        from qrecauda.adaptadores.aer import FuenteAer
        from qrecauda.adaptadores.mthree import TwirlingLectura
    except ImportError as e:
        raise FuenteNoDisponible(f"la demo con Aer necesita el extra «cuantico»: {e}") from e
    modelo = _modelo_de_ruido(ruido)
    shots = shots if shots is not None else DEMO_SHOTS_AER[rapido]
    p = ParametrosPipeline(DEMO_QUBITS, shots)
    ramas = [
        RamaSolicitada("PRNG clasico", FuentePrng(cfg.semilla)),
        RamaSolicitada("Aer sin mitigar (ruido medio)", FuenteAer(cfg.semilla, modelo, 1)),
        RamaSolicitada(
            "Aer con twirling (ruido medio)", FuenteAer(cfg.semilla, modelo, 1), TwirlingLectura(modelo, cfg.semilla, DEMO_BLOQUE, 1)
        ),
    ]  # fmt: skip
    if fuente == "ibm":
        cfg_ibm = replace(cfg, backend="ibm" if not ensayo else "prng", ibm_modo="trabajo")
        ibm = fuente_ibm_de(
            cfg_ibm, conectar, fabricas, ensayo=ensayo, mascaras=DEMO_MASCARAS_IBM,
            max_segundos_qpu=max_segundos_qpu if max_segundos_qpu is not None else TOPE_POR_OMISION_S,
        )  # fmt: skip
        por_pub = DEMO_SHOTS_IBM[rapido] // (DEMO_MASCARAS_IBM + 1)
        c = ContrasteIbm(ibm, DEMO_QUBITS, DEMO_SHOTS_IBM[rapido])
        nombre = "ensayo (fake_sherbrooke)" if ensayo else "IBM"
        ramas += [
            RamaSolicitada(f"{nombre} sin mitigar", c.cruda(), shots=por_pub),
            RamaSolicitada(f"{nombre} con twirling", c.con_twirling(), shots=por_pub * DEMO_MASCARAS_IBM),
        ]
        if ensayo:
            avisos.append("ensayo: backend falso de IBM, sin cuota ni credencial; sus bits los pone Aer, no un dispositivo")
    estimadores = _estimadores_de_demo(cfg, ramas, p, estimador_90b)
    with un_hilo():
        verificar_un_hilo()
        return correr_demo(
            ramas, validador, RelojMonotonico(), p, lambda r: servicio_de(cfg, r), fuente="ensayo" if ensayo else fuente, rapido=rapido,
            avisos=avisos, estimadores=estimadores,
        )  # fmt: skip


def _estimadores_de_demo(
    cfg: Configuracion, ramas: list[RamaSolicitada], p: ParametrosPipeline, estimador_90b: EstimadorDeEntropia | None
) -> dict[str, EstimadorDeEntropia] | None:
    """`mcv`: None (el pipeline de 0.1.0). `conservador`: los estimadores de F5.05 con el 90B y la fuente por vistas de qubit (R.02).

    Falla ANTES de gastar nada si alguna rama no llega al mínimo de bits del 90B, y dice cuántos disparos hacen falta."""
    if cfg.dimensionado == "mcv":
        return None
    try:
        from qrecauda.adaptadores.min_entropia import MUESTRAS_MIN, EstimadorNist90B
    except ImportError as e:
        raise FuenteNoDisponible(f"el dimensionado conservador necesita el extra «validacion» y el 90B: {e}") from e
    cortas = [(r.nombre, p.qubits * (r.shots if r.shots is not None else p.shots)) for r in ramas]
    cortas = [(n, b) for n, b in cortas if b < MUESTRAS_MIN]
    if cortas:
        nombre, bits = min(cortas, key=lambda x: x[1])
        necesarios = -(-MUESTRAS_MIN // p.qubits)
        raise EntradaInvalida(
            f"--dimensionado conservador exige >= {MUESTRAS_MIN} bits por rama (SP 800-90B) y «{nombre}» tiene {bits}: "
            f"con {p.qubits} qubits hacen falta >= {necesarios} disparos por rama (--shots {necesarios}); "
            f"las ramas de hardware reparten pocos disparos a propósito, así que con --fuente ibm usa --dimensionado mcv"
        )
    est = estimadores_conservadores(estimador_90b or EstimadorNist90B(), MUESTRAS_MIN, qubits=p.qubits)
    return est.kw_del_pipeline()


def ejecutor_de(raiz: Path, decl: Declaracion) -> Ejecutor:
    """E1 → C.E1 (cuatro); E2 → C.E2 sobre Aer; E3 → C.E3 (cadena completa); E3b → C.E3b (reserva aparte); el resto, el pipeline."""
    if decl.eureka == "E1":
        return ejecutor_e1_de(raiz)
    if decl.eureka == "E2":
        return ejecutor_e2_de(raiz)
    if decl.eureka == "E3":
        return ejecutor_e3_de(raiz)
    if decl.eureka == "E3b":
        return ejecutor_e3b_de(raiz)
    if decl.eureka == "E5":
        return ejecutor_e5_de(raiz)
    if decl.eureka == "E4":
        return ejecutor_e4_de(raiz, token_ruta=Configuracion.cargar(None).ibm_token_ruta)  # `qrecauda correr`: sin ensayo ni token falla
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
