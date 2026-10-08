"""FuenteDeBits — SamplerV2 sobre hardware IBM con PUBs, twirling de lectura y registro del trabajo (DAG F3.04 y F3.07). Opcional.

Credencial por RUTA (`ibm_token_ruta` / `QRECAUDA_IBM_TOKEN_FILE`), envuelta en `Secreto` desde que se lee: ni repr, ni logs,
ni excepciones la muestran (los mensajes de error del SDK se depuran antes de re-lanzarse). La transpilación a forma ISA
se INYECTA desde la composición (C2: este adaptador no importa `aer`). Sin credencial, sin red o sin extra → `FuenteNoDisponible`.

Verificado leyendo qiskit-ibm-runtime 0.50.0 instalado (no la memoria): `QiskitRuntimeService(channel="ibm_quantum_platform", token=…)`,
`least_busy(min_num_qubits=, operational=, simulator=)`, `SamplerV2.run([(circuito, parametros, shots)])`, `Batch(backend=)`,
`Session(backend=)`, modo «trabajo» (`SamplerV2(mode=backend)`), `job.metrics()` (marcas `created/running/finished`),
`job.usage()` y `service.usage()` (`usage_remaining_seconds`). En 0.50 `SamplerV2` está DEPRECADO a favor de
`qiskit_ibm_runtime.executor_sampler.Sampler`; sigue funcionando y se conserva porque es el que pide el plan.
⚠️ sin verificar contra el servicio real (ninguna llamada a IBM se ha ejecutado aquí): que el plan abierto sólo admita el modo «trabajo»
(Batch y Session son de planes de pago), el formato de las marcas de `metrics()` y el nombre exacto de la cuota en `usage()`.

Twirling de lectura (`mascaras > 0`): el trabajo lleva 1 PUB sin máscara (la medida CRUDA) y `mascaras` PUBs con una máscara X por
qubit, deshecha por XOR clásico tras medir (igual que `mthree.TwirlingLectura`). Todos los PUBs llevan los mismos shots: IBM
deprecó mezclar shots entre PUBs. La máscara se inserta en el circuito YA transpilado (una X nativa antes de cada medición), así que
el layout es el mismo en todos los PUBs y el qubit lógico q es siempre el mismo qubit físico.

Ensayo (`ensayo=True`): el servicio es el local de qiskit-ibm-runtime (`channel="local"`), con backends falsos y sin red, y el
origen es `SIMULADOR_AER`, nunca `HARDWARE_IBM`: un ensayo no puede reclamar origen cuántico (D-002).
"""

from __future__ import annotations

import logging
import sys
import warnings
from collections.abc import Callable
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import qiskit_aer
from numpy.typing import NDArray
from qiskit import QuantumCircuit
from qiskit.exceptions import QiskitError
from qiskit_ibm_runtime.exceptions import IBMError

from qrecauda.datos.hardware import CalibracionQubit, RegistroIbm
from qrecauda.dominio.bits import Bits
from qrecauda.dominio.errores import EntradaInvalida, FuenteNoDisponible
from qrecauda.dominio.muestra import Muestra, Origen, Procedencia
from qrecauda.dominio.presupuesto_qpu import EstimacionQpu, estimar_segundos_qpu, exigir_presupuesto, validar_tope_qpu
from qrecauda.transversal.seguridad import Secreto, describir

# El servicio local fabrica TODOS los backends falsos y uno avisa de que sus errores no son típicos: ruido sin relación con el ensayo.
warnings.filterwarnings("ignore", message="Properties of fake_nighthawk")
_log = logging.getLogger(__name__)

MODOS = ("batch", "session", "trabajo")
CANAL = "ibm_quantum_platform"
MIN_QUBITS_DEL_BACKEND = 8  # al elegir «el menos ocupado» sólo se consideran backends con al menos estos qubits operativos
BACKEND_DE_ENSAYO = "fake_sherbrooke"

# Fallos esperables del SDK y de la red (requests.* hereda de OSError). Todo lo demás (TypeError, KeyError, IndexError, AttributeError…)
# es un error de programación y sube tal cual: disfrazarlo de «comprueba red y token» manda al usuario a buscar donde no es (R.02).
_FALLOS_DEL_SDK = (QiskitError, IBMError, OSError, TimeoutError, RuntimeError, ValueError)
# Lo que puede salir MAL al leer la forma de un resultado remoto (dato externo, no código nuestro): se traduce sólo ahí.
_FORMA_DE_RESULTADO = (KeyError, IndexError, AttributeError, TypeError)

Transpilar = Callable[[QuantumCircuit, Any], Any]  # devuelve el circuito ISA, o algo con `.circuito`, `.via` y `.motivo`
Conectar = Callable[..., Any]  # (secreto) o (secreto, instancia) si se pidió una instancia


@dataclass(frozen=True, slots=True)
class Fabricas:
    """Las piezas del SDK que el adaptador instancia: se sustituyen por dobles en las pruebas (y sólo ahí)."""

    batch: Callable[[Any], Any]  # backend -> contexto Batch
    session: Callable[[Any], Any]  # backend -> contexto Session
    sampler: Callable[..., Any]  # SamplerV2(mode=...)
    version: str  # versión del SDK que va a la Procedencia


def fabricas_reales() -> Fabricas:
    import qiskit_ibm_runtime as rt

    return Fabricas(
        batch=lambda backend: rt.Batch(backend=backend),
        session=lambda backend: rt.Session(backend=backend),
        sampler=rt.SamplerV2,
        version=rt.__version__,
    )


def conectar_real(secreto: Secreto, instancia: str = "") -> Any:
    """Único punto que abre una conexión con IBM. Sólo aquí el valor del secreto sale de su envoltorio.
    `instancia` (CRN o nombre) se pasa tal cual al servicio; vacía ⇒ la que IBM elija por omisión."""
    from qiskit_ibm_runtime import QiskitRuntimeService

    return QiskitRuntimeService(channel=CANAL, token=secreto.revelar(), instance=instancia or None)


def conectar_ensayo(_: Secreto, instancia: str = "") -> Any:
    """El servicio LOCAL de qiskit-ibm-runtime: backends falsos, sin red y sin cuota. El secreto ni se mira."""
    from qiskit_ibm_runtime import QiskitRuntimeService

    return QiskitRuntimeService(channel="local")


@dataclass(frozen=True, slots=True)
class _Preparado:
    backend: Any
    nombre: str
    base: QuantumCircuit  # el ISA sin máscara
    via: str
    motivo: str
    fisicos: tuple[int, ...]
    duracion_s: float


class FuenteIbm:
    """Implementa `FuenteDeBits`: H^⊗n + medición ejecutados en un backend real con SamplerV2 en modo trabajo, Batch o Session."""

    __slots__ = (
        "_avisada_cuota", "_backend", "_conectar", "_ensayo", "_espera_max_s", "_exigir_duracion", "_fabricas", "_gastado_s",
        "_instancia", "_mascaras", "_max_qpu_s", "_modo", "_preparados", "_registros", "_ruta", "_semilla", "_servicio", "_token",
        "_transpilar",
)  # fmt: skip

    def __init__(
        self,
        token: Secreto,
        ruta: Path,
        *,
        transpilar: Transpilar,
        backend: str = "",
        modo: str = "trabajo",
        conectar: Conectar = conectar_real,
        fabricas: Fabricas | None = None,
        mascaras: int = 0,
        semilla: int = 0,
        max_segundos_qpu: float | None = None,
        espera_max_s: float | None = None,
        instancia: str = "",
        ensayo: bool = False,
        exigir_duracion: bool = True,
    ) -> None:
        if modo not in MODOS:
            raise EntradaInvalida(f"modo {modo!r} fuera de {MODOS}")
        if mascaras < 0:
            raise EntradaInvalida(f"las máscaras del twirling no pueden ser negativas, llegó {mascaras}")
        if max_segundos_qpu is not None:
            validar_tope_qpu(max_segundos_qpu)
        self._token, self._ruta = token, ruta
        self._transpilar, self._backend, self._modo = transpilar, backend, modo
        self._conectar, self._fabricas = conectar, fabricas
        self._mascaras, self._semilla, self._max_qpu_s = mascaras, semilla, max_segundos_qpu
        self._espera_max_s, self._instancia, self._ensayo = espera_max_s, instancia, ensayo
        self._exigir_duracion = exigir_duracion and not ensayo  # sólo los dobles de las pruebas la relajan; un ensayo no gasta cuota
        self._avisada_cuota = False
        self._servicio: Any = None  # la conexión se abre en el primer uso, no al construir
        self._preparados: dict[int, _Preparado] = {}
        self._registros: list[RegistroIbm] = []
        self._gastado_s = 0.0

    @classmethod
    def desde_ruta(cls, ruta: Path, *, transpilar: Transpilar, **kw: Any) -> FuenteIbm:
        """Lee la credencial de `ruta`. Falta o vacía ⇒ `FuenteNoDisponible` con la acción a tomar (nunca el contenido)."""
        try:
            token = Secreto.desde_ruta(Path(ruta))
        except EntradaInvalida as e:
            raise FuenteNoDisponible(
                f"no hay credencial de IBM utilizable ({e}): apunta ibm_token_ruta (o QRECAUDA_IBM_TOKEN_FILE) a un fichero "
                f"que contenga el token de IBM Quantum; el valor nunca se pasa por la línea de comandos"
            ) from None
        return cls(token, Path(ruta), transpilar=transpilar, **kw)

    @classmethod
    def para_ensayo(cls, *, transpilar: Transpilar, **kw: Any) -> FuenteIbm:
        """Todo el camino contra el servicio local y un backend falso: sin red, sin cuota y sin credencial."""
        kw.setdefault("conectar", conectar_ensayo)
        kw.setdefault("backend", BACKEND_DE_ENSAYO)
        kw.setdefault("modo", "trabajo")
        return cls(Secreto("ensayo-sin-credencial"), Path("ensayo"), transpilar=transpilar, ensayo=True, **kw)

    def __repr__(self) -> str:
        return (
            f"FuenteIbm(backend={self._backend or 'el menos ocupado'!r}, modo={self._modo!r}, ensayo={self._ensayo!r}, "
            f"token={self._token!r})"
        )

    __str__ = __repr__

    @property
    def registros(self) -> tuple[RegistroIbm, ...]:
        return tuple(self._registros)

    @property
    def ultimo_registro(self) -> RegistroIbm | None:
        return self._registros[-1] if self._registros else None

    @property
    def gastado_estimado_s(self) -> float:
        """Segundos de QPU ya contados contra el tope: el uso real si IBM ya lo calculó, la estimación si no."""
        return self._gastado_s

    # ------------------------------------------------------------------ puerto

    def generar(self, qubits: int, shots: int) -> Muestra:
        """Todos los disparos del trabajo. Con twirling, la muestra va XOR-deshecha y marcada `mitigada`."""
        pubs, registro, pid = self._enviar(qubits, shots)
        todos = np.vstack([p for p in pubs])
        return self._muestra(todos, qubits, registro, pid, mitigada=self._mascaras > 0)

    def generar_contraste(self, qubits: int, shots: int) -> tuple[Muestra, Muestra]:
        """UN trabajo, dos muestras: la CRUDA (el PUB sin máscara) y la del twirling (el resto, deshecho). Exige `mascaras > 0`."""
        if self._mascaras < 1:
            raise EntradaInvalida("generar_contraste necesita mascaras >= 1: sin PUBs con máscara no hay twirling que contrastar")
        pubs, registro, pid = self._enviar(qubits, shots)
        return (
            self._muestra(pubs[0], qubits, registro, pid, mitigada=False),
            self._muestra(np.vstack(pubs[1:]), qubits, registro, pid, mitigada=True),
        )

    def generar_gemelo(self, qubits: int, shots: int) -> tuple[Muestra, Muestra]:
        """CONTROL de E4: los MISMOS circuitos que `generar_contraste` (misma forma ISA, mismos qubits físicos y mismas máscaras) en Aer
        con el ruido que el backend elegido declara (`AerSimulator.from_backend`). Origen `SIMULADOR_AER`: nunca reclama hardware.
        No gasta cuota ni deja registro de trabajo. Sólo modela errores independientes de puerta y lectura, no la deriva ni el
        cross-talk: la diferencia con el dispositivo real es justo lo que E4 mide."""
        if self._mascaras < 1:
            raise EntradaInvalida("generar_gemelo necesita mascaras >= 1: es el gemelo de generar_contraste")
        n_pubs, por_pub = self._reparto(shots)
        prep = self._preparar(qubits)
        mascaras = self._sortear_mascaras(qubits)
        circuitos = [prep.base] + [_con_mascara(prep.base, fila) for fila in mascaras]

        def simular() -> Any:
            from qiskit_aer import AerSimulator
            from qiskit_aer.primitives import SamplerV2 as SamplerAer

            sim = AerSimulator.from_backend(prep.backend)
            return (
                SamplerAer.from_backend(sim, default_shots=por_pub, seed=self._semilla)
                .run([(c, None, por_pub) for c in circuitos])
                .result()
            )

        resultado = self._en_sdk("simular el gemelo en Aer", simular)
        nombre_creg = prep.base.cregs[0].name
        datos = [_a_disparos(resultado[i].data[nombre_creg].get_bitstrings(), qubits, por_pub, "gemelo") for i in range(n_pubs)]
        filas = np.vstack([np.zeros((1, qubits), dtype=np.uint8), mascaras])
        datos = [d ^ f for d, f in zip(datos, filas, strict=True)]
        proc = Procedencia(f"AerSimulator(gemelo de {prep.nombre})", "", qiskit_aer.__version__)

        def muestra(d: NDArray[np.uint8], mitigada: bool) -> Muestra:
            return Muestra(Bits(np.ascontiguousarray(d.T).reshape(-1)), Origen.SIMULADOR_AER, qubits, d.shape[0], mitigada, proc)

        return muestra(datos[0], False), muestra(np.vstack(datos[1:]), True)

    def estimar_qpu(self, qubits: int, shots: int) -> EstimacionQpu:
        """Cuánto QPU costaría UN trabajo así. Conecta, elige backend y transpila; no envía nada."""
        if qubits < 1 or shots < 1:
            raise EntradaInvalida(f"qubits y shots deben ser positivos, llegó {qubits}, {shots}")
        prep = self._preparar(qubits)
        return self._estimacion(prep, *self._reparto(shots))

    def exigir_presupuesto_de(self, qubits: int, shots: int, trabajos: int) -> EstimacionQpu:
        """Aborta (`PresupuestoQpuExcedido`) ANTES de enviar nada si `trabajos` trabajos así no caben en el tope o en la cuota. Sirve para
        que una corrida de varios trabajos no se quede a medias: el primero ya habría gastado cuota y dejado artefactos."""
        if trabajos < 1:
            raise EntradaInvalida(f"trabajos debe ser positivo, llegó {trabajos}")
        unica = self.estimar_qpu(qubits, shots)
        exigir_presupuesto(
            estimado_s=unica.segundos * trabajos,
            tope_s=self._max_qpu_s,
            restante_s=self._cuota_restante(),
            ya_gastado_s=self._gastado_s,
        )
        return unica

    # ------------------------------------------------------------------ envío

    def _reparto(self, shots: int) -> tuple[int, int]:
        """(PUBs, shots por PUB). Sin twirling, un PUB; con él, 1 cruda + `mascaras`, todos con los mismos shots."""
        pubs = 1 + self._mascaras if self._mascaras else 1
        if shots % pubs:
            raise EntradaInvalida(f"{shots} shots no se reparten en {pubs} PUBs iguales (1 cruda + {self._mascaras} máscaras)")
        return pubs, shots // pubs

    def _enviar(self, qubits: int, shots: int) -> tuple[list[NDArray[np.uint8]], RegistroIbm, str]:
        if qubits < 1 or shots < 1:
            raise EntradaInvalida(f"qubits y shots deben ser positivos, llegó {qubits}, {shots}")
        n_pubs, por_pub = self._reparto(shots)
        fabricas = self._fabricas or fabricas_reales()
        prep = self._preparar(qubits)
        estimado = self._estimacion(prep, n_pubs, por_pub)
        exigir_presupuesto(
            estimado_s=estimado.segundos, tope_s=self._max_qpu_s, restante_s=self._cuota_restante(), ya_gastado_s=self._gastado_s
        )
        mascaras = self._sortear_mascaras(qubits)  # (mascaras, qubits); fila de ceros para la cruda
        circuitos = [prep.base] + [_con_mascara(prep.base, fila) for fila in mascaras] if self._mascaras else [prep.base]
        if not self._mascaras:
            mascaras = np.zeros((0, qubits), dtype=np.uint8)
        nombre_creg = prep.base.cregs[0].name
        job_id, job, reservado = "", None, 0.0
        error: FuenteNoDisponible | None = None
        completo = False
        try:
            try:
                if self._modo == "trabajo":
                    contexto: Any = nullcontext(prep.backend)
                else:
                    contexto = (fabricas.batch if self._modo == "batch" else fabricas.session)(prep.backend)
                with contexto as modo:
                    # Sólo `.run()` y `.result()` van en el filtro de fallos del SDK: lo demás es código nuestro y sube tal cual.
                    job = self._en_sdk(
                        f"enviar el trabajo a {prep.nombre}",
                        lambda: fabricas.sampler(mode=modo).run([(c, None, por_pub) for c in circuitos]),
                    )
                    job_id = str(job.job_id() or "")
                    if not job_id:
                        raise FuenteNoDisponible(
                            f"{prep.nombre} no devolvió job_id: sin trabajo real no hay hardware "
                            f"y la muestra no se acepta como HARDWARE_IBM"
                        )
                    if (
                        not self._ensayo
                    ):  # desde que existe el job_id la cuota puede estar corriendo: se cuenta YA y se reconcilia con usage()
                        reservado = estimado.segundos
                        self._gastado_s += reservado
                    _log.info("trabajo %s enviado a %s (%s, %d PUBs × %d shots)", job_id, prep.nombre, self._modo, n_pubs, por_pub)
                    espera = self._espera_max_s if self._espera_max_s and not self._ensayo else None
                    resultado = self._en_sdk(
                        f"obtener la muestra del trabajo {job_id} en {prep.nombre}",
                        lambda: job.result(timeout=espera) if espera else job.result(),
                        job_id,
                    )
                    datos = [self._leer_pub(resultado, i, nombre_creg, qubits, por_pub, job_id) for i in range(n_pubs)]
                completo = True
            finally:
                if not completo:  # también con Ctrl-C: un trabajo que nadie espera sigue gastando cola y cuota
                    self._cancelar(job, job_id)
        except FuenteNoDisponible as e:
            error = e
        if error is not None:
            raise error  # fuera del `except`: sin __context__, la excepción original (que podría citar el token) no viaja
        registro = self._registrar(job, job_id, prep, circuitos, n_pubs, por_pub, estimado, reservado)
        self._registros.append(registro)
        if self._mascaras:  # el twirling se deshace aquí: XOR clásico con la máscara de cada PUB (la cruda lleva ceros)
            datos = [d ^ fila for d, fila in zip(datos, np.vstack([np.zeros((1, qubits), dtype=np.uint8), mascaras]), strict=True)]
        return datos, registro, job_id

    def _muestra(self, disparos: NDArray[np.uint8], qubits: int, registro: RegistroIbm, job_id: str, *, mitigada: bool) -> Muestra:
        bits = Bits(np.ascontiguousarray(disparos.T).reshape(-1))
        proc = Procedencia(registro.backend, job_id, registro.version_sdk)
        origen = Origen.SIMULADOR_AER if self._ensayo else Origen.HARDWARE_IBM
        return Muestra(bits, origen, qubits, disparos.shape[0], mitigada, proc)

    def _sortear_mascaras(self, qubits: int) -> NDArray[np.uint8]:
        rng = np.random.default_rng(self._semilla)
        return rng.integers(0, 2, size=(self._mascaras, qubits), dtype=np.uint8)

    # ------------------------------------------------------------------ preparación (backend, transpilación, calibración)

    def _preparar(self, qubits: int) -> _Preparado:
        if qubits not in self._preparados:
            backend = self._elegir_backend(qubits)
            qc = QuantumCircuit(qubits)
            qc.h(range(qubits))
            qc.measure_all()
            salida = self._en_sdk("la transpilación a forma ISA", lambda: self._transpilar(qc, backend))
            isa = salida if isinstance(salida, QuantumCircuit) else salida.circuito
            via = "local" if isinstance(salida, QuantumCircuit) else str(salida.via)
            motivo = "" if isinstance(salida, QuantumCircuit) else str(salida.motivo)
            fisicos = _qubits_fisicos(isa, qubits)
            try:
                duracion = float(isa.estimate_duration(backend.target, unit="s"))
            except (QiskitError, AttributeError, TypeError, ValueError):
                duracion = 0.0  # un backend sin `target` o sin duraciones: la estimación usaría sólo el retardo de repetición
            if self._exigir_duracion and not duracion > 0.0:
                raise FuenteNoDisponible(
                    f"no se pudo estimar la duración del circuito en {getattr(backend, 'name', '?')} (salió {duracion}): "
                    f"sin ella el tope de QPU "
                    f"subestima el coste y no protege la cuota; elige un backend cuyo target declare duraciones de puerta y de lectura"
                )
            self._comprobar_backend(backend)
            self._preparados[qubits] = _Preparado(backend, str(getattr(backend, "name", "")), isa, via, motivo, fisicos, duracion)
        return self._preparados[qubits]

    def _comprobar_backend(self, backend: Any) -> None:
        """Con twirling, la X nativa tiene que existir en el target del backend: si no, el trabajo con máscaras no sería ISA.
        Un límite que el backend no declara (doble, simulador) no se inventa: se omite."""
        if not self._mascaras:
            return
        ops = getattr(getattr(backend, "target", None), "operation_names", None)
        if ops is not None and "x" not in ops:
            raise FuenteNoDisponible(
                f"el target de {getattr(backend, 'name', '?')} no tiene la puerta «x»: el twirling de lectura inserta una X nativa "
                f"antes de medir y el trabajo no sería ISA; usa --mascaras 0 o elige otro backend"
            )

    @staticmethod
    def _comprobar_limites(backend: Any, n_pubs: int, por_pub: int) -> None:
        """Los PUBs y los disparos por PUB caben en lo que el backend declara (`max_circuits`, `max_shots`), ANTES de enviar nada."""
        for atributo, valor, que in (("max_circuits", n_pubs, "PUBs"), ("max_shots", por_pub, "disparos por PUB")):
            tope = getattr(backend, atributo, None)
            if isinstance(tope, int) and not isinstance(tope, bool) and tope > 0 and valor > tope:
                raise FuenteNoDisponible(
                    f"el trabajo lleva {valor} {que} y {getattr(backend, 'name', '?')} declara {atributo}={tope}: "
                    f"baja los shots o parte el trabajo"
                )

    def _estimacion(self, prep: _Preparado, n_pubs: int, por_pub: int) -> EstimacionQpu:
        self._comprobar_limites(prep.backend, n_pubs, por_pub)
        rep = getattr(prep.backend, "default_rep_delay", None)
        return estimar_segundos_qpu(n_pubs * por_pub, n_pubs, prep.duracion_s, float(rep) if rep else None)

    def _cuota_restante(self) -> float | None:
        """Lo que le queda de cuota a la cuenta, si el servicio lo expone (`usage()['usage_remaining_seconds']`); None si no."""
        if self._ensayo:
            return None
        usar = getattr(self._abrir_servicio(), "usage", None)
        if usar is None:
            self._avisar_sin_cuota("el servicio no expone usage()")
            return None
        try:
            resto = usar().get("usage_remaining_seconds")
        except _FALLOS_DEL_SDK as e:
            self._avisar_sin_cuota(f"no se pudo leer usage() ({type(e).__name__})")
            return None
        if resto is None:
            self._avisar_sin_cuota("usage() no trae la clave «usage_remaining_seconds»")
            return None
        return float(resto)

    def _avisar_sin_cuota(self, motivo: str) -> None:
        """Sin la cuota restante sólo manda el tope pedido: se dice por stderr (una vez), no se calla (R.02)."""
        _log.warning("cuota restante desconocida: %s; sólo manda el tope pedido", motivo)
        if not self._avisada_cuota:
            self._avisada_cuota = True
            print(f"AVISO: cuota restante de QPU desconocida ({motivo}); sólo manda el tope --max-segundos-qpu.", file=sys.stderr)

    def _elegir_backend(self, qubits: int) -> Any:
        servicio = self._abrir_servicio()
        minimo = max(qubits, MIN_QUBITS_DEL_BACKEND)
        if self._backend:
            backend = self._en_sdk(f"elegir el backend {self._backend!r}", lambda: servicio.backend(self._backend))
        elif self._ensayo:
            backend = self._en_sdk("elegir un backend falso", lambda: servicio.least_busy(min_num_qubits=minimo))
        else:
            backend = self._en_sdk(
                "buscar el backend menos ocupado",
                lambda: servicio.least_busy(operational=True, simulator=False, min_num_qubits=minimo),
            )
        disponibles = getattr(backend, "num_qubits", qubits)
        if disponibles < qubits:
            raise FuenteNoDisponible(
                f"el backend {getattr(backend, 'name', '?')} tiene {disponibles} qubits y se piden {qubits}: elige otro con ibm_backend"
            )
        estado = getattr(backend, "status", None)
        if estado is not None:
            operativo = self._en_sdk("leer el estado del backend", lambda: bool(estado().operational))
            if not operativo:
                raise FuenteNoDisponible(f"el backend {getattr(backend, 'name', '?')} no está operativo ahora: elige otro o reintenta")
        return backend

    def _abrir_servicio(self) -> Any:
        if self._servicio is None:
            conectar = (lambda: self._conectar(self._token, self._instancia)) if self._instancia else (lambda: self._conectar(self._token))
            self._servicio = self._en_sdk("conectar con IBM Quantum", conectar)
        return self._servicio

    # ------------------------------------------------------------------ registro

    def _registrar(
        self, job: Any, job_id: str, prep: _Preparado, circuitos: list[QuantumCircuit], n_pubs: int, por_pub: int, estimado: EstimacionQpu,
        reservado: float = 0.0,
    ) -> RegistroIbm:  # fmt: skip
        creado, cola, ejecucion = _tiempos(job)
        uso = _uso(job)
        if uso:  # lo medido por IBM sustituye a lo reservado al recibir el job_id (la estimación sigue valiendo si IBM aún no lo calculó)
            self._gastado_s += uso - reservado
        fecha, calibracion = _calibracion(prep.backend, prep.fisicos)
        import qiskit_ibm_runtime as rt

        return RegistroIbm(
            job_id=job_id, backend=prep.nombre, version_sdk=(self._fabricas.version if self._fabricas else rt.__version__),
            modo=self._modo, ensayo=self._ensayo, shots=n_pubs * por_pub, pubs=n_pubs, mascaras=self._mascaras,
            qubits_fisicos=prep.fisicos, profundidad=max(c.depth() for c in circuitos),
            puertas_dos_qubits=sum(1 for i in prep.base.data if i.operation.num_qubits == 2 and i.operation.name != "barrier"),
            via_transpilacion=prep.via, motivo_transpilacion=prep.motivo, calibracion_fecha=fecha, calibracion=calibracion,
            creado=creado, cola_s=cola, ejecucion_s=ejecucion, uso_qpu_s=uso, estimado_qpu_s=estimado.segundos,
        )  # fmt: skip

    # ------------------------------------------------------------------ errores

    def _en_sdk(self, que: str, accion: Callable[[], Any], job_id: str = "") -> Any:
        error: FuenteNoDisponible | None = None
        try:
            return accion()
        except FuenteNoDisponible:
            raise
        except _FALLOS_DEL_SDK as e:
            error = self._fallo(f"no se pudo {que}", e, job_id)
        raise error  # fuera del `except`: sin __context__ (ver `_enviar`)

    def _leer_pub(self, resultado: Any, i: int, creg: str, qubits: int, esperados: int, job_id: str) -> NDArray[np.uint8]:
        """Los disparos del PUB `i`. La forma del resultado es un dato EXTERNO: si no es la esperada es un fallo del servicio, no un bug."""
        try:
            cadenas = resultado[i].data[creg].get_bitstrings()
        except _FORMA_DE_RESULTADO as e:
            raise FuenteNoDisponible(
                f"el trabajo {job_id} devolvió un resultado con forma inesperada ({type(e).__name__}) en el PUB {i}"
            ) from None
        return _a_disparos(cadenas, qubits, esperados, job_id)

    def _cancelar(self, job: Any, job_id: str) -> None:
        """Pide la cancelación de un trabajo que ya no se espera. Nunca falla: si no se puede, queda dicho en el log y en el mensaje."""
        cancelar = getattr(job, "cancel", None)
        if job is None or not job_id or cancelar is None:
            return
        try:
            cancelar()
            _log.warning("trabajo %s: cancelación pedida porque ya no se espera su resultado", job_id)
        except (*_FALLOS_DEL_SDK, AttributeError, TypeError) as e:  # cancelar es un esfuerzo: el error real es el que ya viaja
            _log.warning("trabajo %s: no se pudo cancelar (%s)", job_id, type(e).__name__)

    def _fallo(self, que: str, e: BaseException, job_id: str = "") -> FuenteNoDisponible:
        """Mensaje accionable y SIN secreto: el texto del SDK se depura; se lanza fuera del `except` (sin encadenar la causa).
        Un error de la API HTTP no vuelca su detalle (el cuerpo puede traer ids o credencial): sólo tipo y status."""
        status = _status_http(e)
        if status is not None or isinstance(e, IBMError):
            detalle = f"{type(e).__name__} (HTTP {status if status is not None else '?'}; el detalle de la respuesta no se muestra)"
        else:
            detalle = f"{type(e).__name__}: " + str(e).replace(self._token.revelar(), describir(self._token.revelar()))
        pista = (
            f" Se pidió cancelar el trabajo {job_id}; si sigue en la cola de IBM, recupéralo con QiskitRuntimeService.job({job_id!r})."
            if job_id and not self._ensayo
            else ""
        )
        return FuenteNoDisponible(
            f"{que}: {detalle}. "
            f"Comprueba la conexión de red, que el token de {self._ruta} sea válido y que tengas acceso al backend.{pista}"
        )


# ------------------------------------------------------------------ funciones puras sobre circuitos y resultados


def _status_http(e: BaseException) -> int | None:
    """El código HTTP de un error de la API (`requests` lo cuelga en `.response`; otros SDK en `.status_code`), o None si no es de HTTP."""
    for fuente in (getattr(e, "response", None), e):
        v = getattr(fuente, "status_code", None)
        if isinstance(v, int) and not isinstance(v, bool):
            return v
    return None


def _con_mascara(isa: QuantumCircuit, mascara: NDArray[np.uint8]) -> QuantumCircuit:
    """Copia de `isa` con una X nativa justo antes de la medición de cada qubit lógico cuya máscara vale 1 (layout intacto)."""
    nuevo = isa.copy_empty_like()
    for inst in isa.data:
        if inst.operation.name == "measure" and mascara[isa.find_bit(inst.clbits[0]).index]:
            nuevo.x(inst.qubits[0])
        nuevo.append(inst)
    return nuevo


def _qubits_fisicos(isa: QuantumCircuit, qubits: int) -> tuple[int, ...]:
    """Para cada qubit lógico (su clbit de `measure_all`), el qubit FÍSICO que lo mide en el circuito ISA."""
    mapa: dict[int, int] = {}
    for inst in isa.data:
        if inst.operation.name == "measure":
            mapa[isa.find_bit(inst.clbits[0]).index] = isa.find_bit(inst.qubits[0]).index
    if sorted(mapa) != list(range(qubits)):
        raise FuenteNoDisponible(f"el circuito ISA mide {sorted(mapa)} y se esperaban los {qubits} qubits lógicos")
    return tuple(mapa[q] for q in range(qubits))


def _a_disparos(cadenas: list[str], qubits: int, esperados: int, job_id: str) -> NDArray[np.uint8]:
    """(shots, qubits) con la columna k = qubit k. Cada cadena es big-endian: el carácter 0 es el clbit n-1."""
    if len(cadenas) != esperados:
        raise FuenteNoDisponible(f"el trabajo {job_id} devolvió {len(cadenas)} disparos y se pidieron {esperados}")
    if any(len(c) != qubits for c in cadenas):
        raise FuenteNoDisponible(f"el trabajo {job_id} devolvió cadenas de anchura distinta de {qubits} qubits")
    crudo = np.frombuffer("".join(cadenas).encode("ascii"), dtype=np.uint8).reshape(len(cadenas), qubits)
    return np.ascontiguousarray((crudo[:, ::-1] == ord("1")).astype(np.uint8))


def _qubit_mayor(cadenas: list[str], n: int) -> Any:
    """Bits en orden QUBIT-MAYOR (el mismo que FuenteAer): cada cadena es big-endian, el carácter 0 es el clbit n-1."""
    return np.ascontiguousarray(_a_disparos(cadenas, n, len(cadenas), "").T).reshape(-1)


def _como_fecha(v: object) -> datetime | None:
    if isinstance(v, datetime):
        return v
    if isinstance(v, str) and v:
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _tiempos(job: Any) -> tuple[str, float | None, float | None]:
    """(creado ISO, segundos en cola, segundos de ejecución) de `job.metrics()['timestamps']`; ('', None, None) si no los hay."""
    try:
        marcas = job.metrics().get("timestamps", {})
    except (*_FALLOS_DEL_SDK, AttributeError):
        return "", None, None
    creado, corre, fin = (_como_fecha(marcas.get(k)) for k in ("created", "running", "finished"))
    cola = (corre - creado).total_seconds() if creado and corre else None
    ejecucion = (fin - corre).total_seconds() if fin and corre else None
    return (creado.isoformat() if creado else ""), cola, ejecucion


def _uso(job: Any) -> float | None:
    """Lo que IBM cargó por el trabajo (`job.usage()`), si ya lo calculó; None si no (0 significa «aún pendiente»)."""
    try:
        v = job.usage()
    except (*_FALLOS_DEL_SDK, AttributeError):
        return None
    return float(v) if v else None


def _calibracion(backend: Any, fisicos: tuple[int, ...]) -> tuple[str, tuple[CalibracionQubit, ...]]:
    """Fecha de la calibración y T1/T2/error de lectura de cada qubit físico usado, de `backend.target`/`backend.properties()`."""
    fecha = ""
    try:
        props = backend.properties()
        ultima = getattr(props, "last_update_date", None)
        fecha = ultima.isoformat() if ultima is not None else ""
    except (*_FALLOS_DEL_SDK, AttributeError):
        pass
    filas: list[CalibracionQubit] = []
    try:
        target = backend.target
        for q in fisicos:
            qp = target.qubit_properties[q] if target.qubit_properties else None
            prop_lectura = target["measure"].get((q,)) if "measure" in target.operation_names else None
            filas.append(
                CalibracionQubit(
                    q,
                    getattr(qp, "t1", None),
                    getattr(qp, "t2", None),
                    getattr(prop_lectura, "error", None),
                )
            )
    except (*_FALLOS_DEL_SDK, AttributeError):
        filas = [CalibracionQubit(q, None, None, None) for q in fisicos]
    return fecha, tuple(filas)
