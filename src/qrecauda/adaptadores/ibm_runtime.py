"""FuenteDeBits — SamplerV2 sobre hardware IBM con PUBs y Batch/Session (DAG F3.04). Opcional: la demo no depende de él.

Credencial por RUTA (`ibm_token_ruta` / `QRECAUDA_IBM_TOKEN_FILE`), envuelta en `Secreto` desde que se lee: ni repr, ni logs,
ni excepciones la muestran (los mensajes de error del SDK se depuran antes de re-lanzarse). La transpilación a forma ISA
se INYECTA desde la composición (C2: este adaptador no importa `aer`). Sin credencial, sin red o sin extra → `FuenteNoDisponible`.

⚠️ sin verificar contra hardware (la corrida real es F3.06): el canal `ibm_quantum_platform`, `least_busy(...)` y `Batch(backend=...)`
siguen la API de qiskit-ibm-runtime 0.50 documentada, pero ninguna llamada a IBM se ha ejecutado aquí.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from qiskit import QuantumCircuit
from qiskit.exceptions import QiskitError
from qiskit_ibm_runtime.exceptions import IBMError

from qrecauda.dominio.bits import Bits
from qrecauda.dominio.errores import EntradaInvalida, FuenteNoDisponible
from qrecauda.dominio.muestra import Muestra, Origen, Procedencia
from qrecauda.transversal.seguridad import Secreto, describir

_log = logging.getLogger(__name__)

MODOS = ("batch", "session")
CANAL = "ibm_quantum_platform"

# Fallos esperables del SDK y de la red (requests.* hereda de OSError). Todo lo demás es un error de programación y sube tal cual.
_FALLOS_DEL_SDK = (QiskitError, IBMError, OSError, TimeoutError, RuntimeError, ValueError, TypeError, KeyError, AttributeError, IndexError)

Transpilar = Callable[[QuantumCircuit, Any], QuantumCircuit]
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


class FuenteIbm:
    """Implementa `FuenteDeBits`: H^⊗n + medición ejecutados en un backend real con SamplerV2 dentro de un Batch o una Session."""

    __slots__ = ("_backend", "_conectar", "_fabricas", "_modo", "_ruta", "_servicio", "_token", "_transpilar")

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
    ) -> None:
        if modo not in MODOS:
            raise EntradaInvalida(f"modo {modo!r} fuera de {MODOS}")
        self._token, self._ruta = token, ruta
        self._transpilar, self._backend, self._modo = transpilar, backend, modo
        self._conectar, self._fabricas = conectar, fabricas
        self._servicio: Any = None  # la conexión se abre en el primer `generar`, no al construir

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

    def __repr__(self) -> str:
        return f"FuenteIbm(backend={self._backend or 'el menos ocupado'!r}, modo={self._modo!r}, token={self._token!r})"

    __str__ = __repr__

    # ------------------------------------------------------------------ puerto

    def generar(self, qubits: int, shots: int) -> Muestra:
        if qubits < 1 or shots < 1:
            raise EntradaInvalida(f"qubits y shots deben ser positivos, llegó {qubits}, {shots}")
        fabricas = self._fabricas or fabricas_reales()
        backend = self._elegir_backend(qubits)
        nombre = str(getattr(backend, "name", ""))
        qc = QuantumCircuit(qubits)
        qc.h(range(qubits))
        qc.measure_all()
        isa = self._en_sdk("la transpilación a forma ISA", lambda: self._transpilar(qc, backend))
        job_id = ""
        error: FuenteNoDisponible | None = None
        try:
            contexto = (fabricas.batch if self._modo == "batch" else fabricas.session)(backend)
            with contexto as modo:
                job = fabricas.sampler(mode=modo).run([(isa, None, shots)])
                job_id = str(job.job_id() or "")
                if not job_id:
                    raise FuenteNoDisponible(
                        f"{nombre} no devolvió job_id: sin trabajo real no hay hardware y la muestra no se acepta como HARDWARE_IBM"
                    )
                _log.info("trabajo %s enviado a %s (%s, %d shots)", job_id, nombre, self._modo, shots)
                cadenas = job.result()[0].data[isa.cregs[0].name].get_bitstrings()
                if len(cadenas) != shots:
                    raise FuenteNoDisponible(f"el trabajo {job_id} devolvió {len(cadenas)} disparos y se pidieron {shots}")
                if any(len(c) != qubits for c in cadenas):
                    raise FuenteNoDisponible(f"el trabajo {job_id} devolvió cadenas de anchura distinta de {qubits} qubits")
        except FuenteNoDisponible:
            raise
        except _FALLOS_DEL_SDK as e:
            error = self._fallo(f"el trabajo{f' {job_id}' if job_id else ''} en {nombre} no entregó una muestra", e)
        if error is not None:
            raise error  # fuera del `except`: sin __context__, la excepción original (que podría citar el token) no viaja
        return Muestra(
            Bits(_qubit_mayor(cadenas, qubits)), Origen.HARDWARE_IBM, qubits, shots, False, Procedencia(nombre, job_id, fabricas.version)
        )

    # ------------------------------------------------------------------ internos

    def _elegir_backend(self, qubits: int) -> Any:
        servicio = self._abrir_servicio()
        if self._backend:
            backend = self._en_sdk(f"elegir el backend {self._backend!r}", lambda: servicio.backend(self._backend))
        else:
            backend = self._en_sdk(
                "buscar el backend menos ocupado",
                lambda: servicio.least_busy(operational=True, simulator=False, min_num_qubits=qubits),
            )
        disponibles = getattr(backend, "num_qubits", qubits)
        if disponibles < qubits:
            raise FuenteNoDisponible(
                f"el backend {getattr(backend, 'name', '?')} tiene {disponibles} qubits y se piden {qubits}: elige otro con ibm_backend"
            )
        return backend

    def _abrir_servicio(self) -> Any:
        if self._servicio is None:
            self._servicio = self._en_sdk("conectar con IBM Quantum", lambda: self._conectar(self._token))
        return self._servicio

    def _en_sdk(self, que: str, accion: Callable[[], Any]) -> Any:
        error: FuenteNoDisponible | None = None
        try:
            return accion()
        except FuenteNoDisponible:
            raise
        except _FALLOS_DEL_SDK as e:
            error = self._fallo(f"no se pudo {que}", e)
        raise error  # fuera del `except`: sin __context__ (ver `generar`)

    def _fallo(self, que: str, e: BaseException) -> FuenteNoDisponible:
        """Mensaje accionable y SIN secreto: el texto del SDK se depura; se lanza fuera del `except` (sin encadenar la causa)."""
        detalle = str(e).replace(self._token.revelar(), describir(self._token.revelar()))
        return FuenteNoDisponible(
            f"{que}: {type(e).__name__}: {detalle}. "
            f"Comprueba la conexión de red, que el token de {self._ruta} sea válido y que tengas acceso al backend"
        )


def _qubit_mayor(cadenas: list[str], n: int) -> Any:
    """Bits en orden QUBIT-MAYOR (el mismo que FuenteAer): cada cadena es big-endian, el carácter 0 es el clbit n-1."""
    disparos = np.array([[c[n - 1 - k] == "1" for k in range(n)] for c in cadenas], dtype=np.uint8)  # (shots, n)
    return np.ascontiguousarray(disparos.T).reshape(-1)
