"""FuenteDeBits — circuito H^⊗n + medición sobre AerSimulator con modelo de ruido (DAG F3.01). ⚠️ El muestreo de
Aer es pseudoaleatorio: su salida se marca Origen.SIMULADOR_AER y nunca reclama origen cuántico (D-002, spike S.03).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import qiskit_aer
from numpy.typing import NDArray
from qiskit import QuantumCircuit
from qiskit.exceptions import QiskitError
from qiskit_aer.primitives import SamplerV2

from qrecauda.dominio.bits import Bits
from qrecauda.dominio.errores import EntradaInvalida, FuenteNoDisponible
from qrecauda.dominio.muestra import Muestra, Origen, Procedencia


class FuenteAer:
    """Implementa `FuenteDeBits`. Con `semilla` explícita es determinista (es un PRNG); con `semilla=None` Aer elige la suya."""

    def __init__(self, semilla: int | None = None, noise_model: Any | None = None, max_parallel_threads: int | None = None) -> None:
        if max_parallel_threads is not None and max_parallel_threads < 1:
            raise EntradaInvalida(f"max_parallel_threads debe ser positivo, llegó {max_parallel_threads}")
        self._semilla = semilla
        self._noise_model = noise_model
        self._hilos = max_parallel_threads  # P.E3: «un hilo» también en el OpenMP propio de Aer

    def generar(self, qubits: int, shots: int) -> Muestra:
        if qubits < 1 or shots < 1:
            raise EntradaInvalida(f"qubits y shots deben ser positivos, llegó {qubits}, {shots}")
        qc = QuantumCircuit(qubits)
        qc.h(range(qubits))
        qc.measure_all()
        bits = self._muestrear(qc, shots)
        proc = Procedencia(backend="AerSimulator", version=qiskit_aer.__version__)
        return Muestra(Bits(bits), Origen.SIMULADOR_AER, qubits, shots, False, proc)

    def _opciones_backend(self) -> dict[str, Any] | None:
        opciones: dict[str, Any] = {}
        if self._noise_model is not None:
            opciones["noise_model"] = self._noise_model
        if self._hilos is not None:
            opciones["max_parallel_threads"] = self._hilos
        return {"backend_options": opciones} if opciones else None

    def _muestrear(self, circuito: QuantumCircuit, shots: int) -> NDArray[np.uint8]:
        """Bits en orden QUBIT-MAYOR: todos los disparos del qubit 0, luego los del qubit 1…"""
        opciones = self._opciones_backend()
        try:
            sampler = SamplerV2(default_shots=shots, seed=self._semilla, options=opciones)
            resultado = sampler.run([(circuito,)]).result()
            cadenas = resultado[0].data[circuito.cregs[0].name].get_bitstrings()
        except (QiskitError, ValueError, TypeError, KeyError, AttributeError) as e:  # se traducen a un error del dominio
            raise FuenteNoDisponible(f"AerSimulator no pudo muestrear: {e}") from e
        n = circuito.num_qubits
        # cada cadena es big-endian: el carácter 0 es el clbit n-1 ⇒ se invierte para que la columna k sea el qubit k
        disparos = np.array([[c[n - 1 - k] == "1" for k in range(n)] for c in cadenas], dtype=np.uint8)  # (shots, n)
        return np.ascontiguousarray(disparos.T).reshape(-1)
