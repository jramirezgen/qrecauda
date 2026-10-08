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
from collections.abc import Callable
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from qiskit import QuantumCircuit
from qiskit.exceptions import QiskitError
from qiskit_ibm_runtime.exceptions import IBMError

from qrecauda.datos.hardware import CalibracionQubit, RegistroIbm
from qrecauda.dominio.bits import Bits
from qrecauda.dominio.errores import EntradaInvalida, FuenteNoDisponible
from qrecauda.dominio.muestra import Muestra, Origen, Procedencia
from qrecauda.dominio.presupuesto_qpu import EstimacionQpu, estimar_segundos_qpu, exigir_presupuesto
from qrecauda.transversal.seguridad import Secreto, describir

_log = logging.getLogger(__name__)

MODOS = ("batch", "session", "trabajo")
CANAL = "ibm_quantum_platform"
MIN_QUBITS_DEL_BACKEND = 8  # al elegir «el menos ocupado» sólo se consideran backends con al menos estos qubits operativos
BACKEND_DE_ENSAYO = "fake_sherbrooke"

# Fallos esperables del SDK y de la red (requests.* hereda de OSError). Todo lo demás es un error de programación y sube tal cual.
_FALLOS_DEL_SDK = (QiskitError, IBMError, OSError, TimeoutError, RuntimeError, ValueError, TypeError, KeyError, AttributeError, IndexError)

Transpilar = Callable[[QuantumCircuit, Any], Any]  # devuelve el circuito ISA, o algo con `.circuito`, `.via` y `.motivo`
Conectar = Callable[[Secreto], Any]


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


def conectar_real(secreto: Secreto) -> Any:
    """Único punto que abre una conexión con IBM. Sólo aquí el valor del secreto sale de su envoltorio."""
    from qiskit_ibm_runtime import QiskitRuntimeService

    return QiskitRuntimeService(channel=CANAL, token=secreto.revelar())


def conectar_ensayo(_: Secreto) -> Any:
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
        "_backend", "_conectar", "_ensayo", "_espera_max_s", "_fabricas", "_gastado_s", "_instancia", "_mascaras", "_max_qpu_s", "_modo",
        "_preparados", "_registros", "_ruta", "_semilla", "_servicio", "_token", "_transpilar",
    )  # fmt: skip

    def __init__(
        self,
        token: Secreto,
        ruta: Path,
        *,
        transpilar: Transpilar,
        backend: str = "",
        modo: str = "batch",
        conectar: Conectar = conectar_real,
        fabricas: Fabricas | None = None,
        mascaras: int = 0,
        semilla: int = 0,
        max_segundos_qpu: float | None = None,
        espera_max_s: float | None = None,
        instancia: str = "",
        ensayo: bool = False,
    ) -> None:
        if modo not in MODOS:
            raise EntradaInvalida(f"modo {modo!r} fuera de {MODOS}")
        if mascaras < 0:
            raise EntradaInvalida(f"las máscaras del twirling no pueden ser negativas, llegó {mascaras}")
        if max_segundos_qpu is not None and max_segundos_qpu <= 0:
            raise EntradaInvalida(f"max_segundos_qpu debe ser positivo, llegó {max_segundos_qpu}")
        self._token, self._ruta = token, ruta
        self._transpilar, self._backend, self._modo = transpilar, backend, modo
        self._conectar, self._fabricas = conectar, fabricas
        self._mascaras, self._semilla, self._max_qpu_s = mascaras, semilla, max_segundos_qpu
        self._espera_max_s, self._instancia, self._ensayo = espera_max_s, instancia, ensayo
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

    def estimar_qpu(self, qubits: int, shots: int) -> EstimacionQpu:
        """Cuánto QPU costaría UN trabajo así. Conecta, elige backend y transpila; no envía nada."""
        if qubits < 1 or shots < 1:
            raise EntradaInvalida(f"qubits y shots deben ser positivos, llegó {qubits}, {shots}")
        prep = self._preparar(qubits)
        return self._estimacion(prep, *self._reparto(shots))

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
        job_id, job = "", None
        error: FuenteNoDisponible | None = None
        try:
            if self._modo == "trabajo":
                contexto: Any = nullcontext(prep.backend)
            else:
                contexto = (fabricas.batch if self._modo == "batch" else fabricas.session)(prep.backend)
            with contexto as modo:
                job = fabricas.sampler(mode=modo).run([(c, None, por_pub) for c in circuitos])
                job_id = str(job.job_id() or "")
                if not job_id:
                    raise FuenteNoDisponible(
                        f"{prep.nombre} no devolvió job_id: sin trabajo real no hay hardware y la muestra no se acepta como HARDWARE_IBM"
                    )
                _log.info("trabajo %s enviado a %s (%s, %d PUBs × %d shots)", job_id, prep.nombre, self._modo, n_pubs, por_pub)
                resultado = job.result(timeout=self._espera_max_s) if self._espera_max_s and not self._ensayo else job.result()
                datos = [_a_disparos(resultado[i].data[nombre_creg].get_bitstrings(), qubits, por_pub, job_id) for i in range(n_pubs)]
        except FuenteNoDisponible:
            raise
        except _FALLOS_DEL_SDK as e:
            error = self._fallo(f"el trabajo{f' {job_id}' if job_id else ''} en {prep.nombre} no entregó una muestra", e, job_id)
        if error is not None:
            raise error  # fuera del `except`: sin __context__, la excepción original (que podría citar el token) no viaja
        registro = self._registrar(job, job_id, prep, circuitos, n_pubs, por_pub, estimado)
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
                duracion = 0.0  # un backend sin `target` o sin duraciones: la estimación usa sólo el retardo de repetición
            self._preparados[qubits] = _Preparado(backend, str(getattr(backend, "name", "")), isa, via, motivo, fisicos, duracion)
        return self._preparados[qubits]

    def _estimacion(self, prep: _Preparado, n_pubs: int, por_pub: int) -> EstimacionQpu:
        rep = getattr(prep.backend, "default_rep_delay", None)
        return estimar_segundos_qpu(n_pubs * por_pub, n_pubs, prep.duracion_s, float(rep) if rep else None)

    def _cuota_restante(self) -> float | None:
        """Lo que le queda de cuota a la cuenta, si el servicio lo expone (`usage()['usage_remaining_seconds']`); None si no."""
        if self._ensayo:
            return None
        usar = getattr(self._abrir_servicio(), "usage", None)
        if usar is None:
            return None
        try:
            resto = usar().get("usage_remaining_seconds")
        except _FALLOS_DEL_SDK as e:
            _log.warning("no se pudo leer la cuota del servicio (%s): sólo manda el tope pedido", type(e).__name__)
            return None
        return None if resto is None else float(resto)

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
            self._servicio = self._en_sdk("conectar con IBM Quantum", lambda: self._conectar(self._token))
        return self._servicio

    # ------------------------------------------------------------------ registro

    def _registrar(
        self, job: Any, job_id: str, prep: _Preparado, circuitos: list[QuantumCircuit], n_pubs: int, por_pub: int, estimado: EstimacionQpu
    ) -> RegistroIbm:
        creado, cola, ejecucion = _tiempos(job)
        uso = _uso(job)
        self._gastado_s += uso if uso else (0.0 if self._ensayo else estimado.segundos)
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

    def _en_sdk(self, que: str, accion: Callable[[], Any]) -> Any:
        error: FuenteNoDisponible | None = None
        try:
            return accion()
        except FuenteNoDisponible:
            raise
        except _FALLOS_DEL_SDK as e:
            error = self._fallo(f"no se pudo {que}", e)
        raise error  # fuera del `except`: sin __context__ (ver `_enviar`)

    def _fallo(self, que: str, e: BaseException, job_id: str = "") -> FuenteNoDisponible:
        """Mensaje accionable y SIN secreto: el texto del SDK se depura; se lanza fuera del `except` (sin encadenar la causa)."""
        detalle = str(e).replace(self._token.revelar(), describir(self._token.revelar()))
        pista = (
            f" El trabajo {job_id} puede seguir en la cola de IBM: recupéralo con QiskitRuntimeService.job({job_id!r})."
            if job_id and not self._ensayo
            else ""
        )
        return FuenteNoDisponible(
            f"{que}: {type(e).__name__}: {detalle}. "
            f"Comprueba la conexión de red, que el token de {self._ruta} sea válido y que tengas acceso al backend.{pista}"
        )


# ------------------------------------------------------------------ funciones puras sobre circuitos y resultados


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
