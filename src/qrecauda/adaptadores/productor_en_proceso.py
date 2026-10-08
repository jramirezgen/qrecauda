"""ProductorDeClaves en un proceso aparte (F6.03): `multiprocessing` con `spawn`, una cola acotada y la clave sólo en memoria.

El hijo construye su propio generador con la `fabrica` (que fija su núcleo y su único hilo, y elige los adaptadores; la compone
`composicion`), produce claves una tras otra y las encola. La cola es acotada: con `capacidad` claves esperando, el hijo se
bloquea (contrapresión) y ese tiempo se mide aparte, para que la tasa del productor no dependa de lo lento que consuma el otro.

La clave cruza empaquetada en bytes (`np.packbits`); nunca se escribe a disco ni se imprime. Las metas (sin clave) y el informe
final viajan por una cola de control sin tope. Lo que el hijo no puede decir de sí mismo (p. ej. si lo matan) lo dice el padre.
"""

from __future__ import annotations

import multiprocessing as mp
import os
import queue
import resource
import signal
import sys
import time
from collections.abc import Callable
from typing import Any

import numpy as np

from qrecauda.datos import ClaveEntregada, InformeDelProductor, MetaClave
from qrecauda.dominio.bits import Bits
from qrecauda.dominio.errores import CorridaInvalida, EntradaInvalida
from qrecauda.puertos import GeneradorDeClaves

SONDEO_S = 0.2  # cada cuánto el consumidor mira si el hijo sigue vivo mientras espera una clave
SONDEO_PUT_S = 0.25  # cada cuánto el hijo bloqueado en la cola mira si le piden parar
ESPERA_DE_PARADA_S = 120.0  # lo que el padre da al hijo para terminar la clave en curso antes de matarlo
MAX_MENSAJE_DE_ERROR = 500  # tipo y mensaje de la excepción cruzan el canal de control; nunca la clave ni la muestra


def _padre_vivo() -> bool:
    """Un hijo cuyo padre murió (kill -9, OOM) no tiene a quién entregar claves: debe salir, no quedar huérfano produciendo."""
    padre = mp.parent_process()
    return padre is None or padre.is_alive()


def _salir_limpio(_senal: int, _marco: object) -> None:
    sys.exit(1)  # SIGTERM del padre: deja correr los `finally` (informe, y matar el grupo del 90B en curso)


def _cpu_con_hijos_ns() -> int:
    propio, hijos = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)  # µs, no ticks de 10 ms
    return round((propio.ru_utime + propio.ru_stime + hijos.ru_utime + hijos.ru_stime) * 1e9)


def _empaquetar(e: ClaveEntregada) -> tuple[bytes, int, dict[str, object], str, str]:
    return np.packbits(e.clave.datos).tobytes(), len(e.clave), e.meta.a_mapa(), e.rotulo, e.origen


def _desempaquetar(carga: tuple[bytes, int, dict[str, object], str, str]) -> ClaveEntregada:
    crudo, nbits, meta, rotulo, origen = carga
    return ClaveEntregada(Bits(np.unpackbits(np.frombuffer(crudo, dtype=np.uint8))[:nbits]), MetaClave.desde_mapa(meta), rotulo, origen)


def _bucle_del_hijo(fabrica: Callable[[], GeneradorDeClaves], cola: Any, control: Any, parar: Any) -> None:
    """Cuerpo del proceso productor. Todo fallo esperado se informa por `control`; el resto lo cuenta el código de salida."""
    pared0, cpu0, cpu_p0 = time.perf_counter_ns(), _cpu_con_hijos_ns(), time.process_time_ns()
    metas: list[MetaClave] = []
    nucleos: tuple[int, ...] = ()
    signal.signal(signal.SIGTERM, _salir_limpio)
    try:
        generador = fabrica()
        nucleos = tuple(sorted(os.sched_getaffinity(0)))
        indice = 0
        while not parar.is_set() and _padre_vivo():
            entregada = generador.generar(indice)
            b0, encolada = time.perf_counter_ns(), False
            while not parar.is_set() and _padre_vivo():
                try:
                    cola.put(_empaquetar(entregada), timeout=SONDEO_PUT_S)
                    encolada = True
                    break
                except queue.Full:
                    continue
            metas.append(entregada.meta.con_bloqueo(time.perf_counter_ns() - b0, encolada))
            indice += 1
    finally:
        exc = sys.exc_info()[1]  # cualquier excepción, esperada o no: tipo y mensaje (sin datos) al padre; la propaga igual
        if exc is not None and not isinstance(exc, SystemExit):
            control.put(("error", f"{type(exc).__name__}: {exc}"[:MAX_MENSAJE_DE_ERROR]))
        elif isinstance(exc, SystemExit):
            control.put(("error", "el proceso productor recibió la orden de terminar"))
        informe = InformeDelProductor(
            nucleos or tuple(sorted(os.sched_getaffinity(0))),
            time.perf_counter_ns() - pared0,
            _cpu_con_hijos_ns() - cpu0,
            time.process_time_ns() - cpu_p0,
            tuple(metas),
        )
        control.put(("informe", informe.a_mapa()))
        cola.cancel_join_thread()  # lo que quedó sin enviar no le importa a nadie: sin esto el hijo no sale con la cola llena


class ProductorEnProceso:
    """Implementa `ProductorDeClaves`."""

    def __init__(self, fabrica: Callable[[], GeneradorDeClaves], capacidad: int, espera_de_parada_s: float = ESPERA_DE_PARADA_S) -> None:
        if capacidad < 1:
            raise EntradaInvalida(f"la cola del productor admite al menos 1 clave, llegó {capacidad}")
        self._fabrica, self._capacidad, self._espera_parada = fabrica, capacidad, espera_de_parada_s
        self._proceso: Any = None
        self._cola: Any = None
        self._control: Any = None
        self._parar: Any = None
        self._informe: InformeDelProductor | None = None
        self._error: str | None = None

    # ------------------------------------------------------------------ ciclo de vida

    def iniciar(self) -> None:
        if self._proceso is not None:
            raise EntradaInvalida("el productor ya se inició")
        ctx = mp.get_context("spawn")  # nunca fork: el padre puede tener OpenMP/BLAS inicializados
        self._cola, self._control, self._parar = ctx.Queue(self._capacidad), ctx.Queue(), ctx.Event()
        self._proceso = ctx.Process(
            target=_bucle_del_hijo, args=(self._fabrica, self._cola, self._control, self._parar), name="qrecauda-productor", daemon=True
        )
        self._proceso.start()

    def tomar(self, espera_s: float | None) -> ClaveEntregada | None:
        if self._proceso is None:
            raise EntradaInvalida("el productor no se inició")
        limite = None if espera_s is None else time.monotonic() + espera_s
        while True:
            self._vigilar()
            resto = SONDEO_S if limite is None else min(SONDEO_S, max(0.0, limite - time.monotonic()))
            try:
                carga = self._cola.get(timeout=resto) if resto > 0 else self._cola.get_nowait()
            except queue.Empty:
                if limite is not None and time.monotonic() >= limite:
                    return None
                if not self._proceso.is_alive():
                    self._vigilar(muerto=True)
                continue
            return _desempaquetar(carga)

    def listas(self) -> int:
        return int(self._cola.qsize()) if self._cola is not None else 0

    def detener(self) -> InformeDelProductor:
        if self._proceso is None:  # idempotente: se llama en un `finally`, y si `iniciar` no llegó a correr no debe tapar el error real
            return InformeDelProductor((), 0, 0, 0, (), forzado=False)
        if self._informe is not None:
            return self._informe
        self._parar.set()
        self._proceso.join(self._espera_parada)
        forzado = self._proceso.is_alive()
        if forzado:
            self._proceso.terminate()
            self._proceso.join(10.0)
        self._leer_control(bloqueante=not forzado)
        self._cola.close()
        self._control.close()
        if self._informe is None:
            self._informe = InformeDelProductor((), 0, 0, 0, (), forzado=True)
        elif forzado:
            self._informe = InformeDelProductor(
                self._informe.nucleos, self._informe.pared_ns, self._informe.cpu_ns, self._informe.cpu_proceso_ns,
                self._informe.claves, forzado=True,
            )  # fmt: skip
        return self._informe

    # ------------------------------------------------------------------ vigilancia

    def _leer_control(self, bloqueante: bool = False) -> None:
        while True:
            try:
                tipo, carga = self._control.get(timeout=5.0) if bloqueante and self._informe is None else self._control.get_nowait()
            except queue.Empty:
                return
            if tipo == "error":
                self._error = str(carga)
            elif tipo == "informe":
                self._informe = InformeDelProductor.desde_mapa(carga)

    def _vigilar(self, muerto: bool = False) -> None:
        self._leer_control()
        if self._error is not None:
            raise CorridaInvalida(f"el proceso productor falló: {self._error}")
        if muerto or (self._proceso is not None and not self._proceso.is_alive() and self._informe is not None):
            raise CorridaInvalida(
                f"el proceso productor terminó (código {self._proceso.exitcode}) antes de entregar la clave que se esperaba"
            )
