"""Modelo de ruido del backend simulado: lectura asimétrica, relajación (DAG F3.02). Lo consume el adaptador aer.

Alcance declarado:
- Lectura: matriz de confusión (`CanalLectura`) -> `ReadoutError`. Tres niveles sintéticos con nombre.
- Relajación: `thermal_relaxation_error` opcional sobre la puerta H.
- Cross-talk: NO modelado (Aer no lo trae como canal sencillo; sin un acoplamiento medido sería inventar parámetros).
- Pauli-Lindblad y NoiseLearnerV3: no aplicables en local (viven en el servicio de IBM).
- Nivel realista: `NoiseModel.from_backend` sobre un backend falso de `qiskit_ibm_runtime.fake_provider`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray
from qiskit_aer.noise import NoiseModel, ReadoutError, thermal_relaxation_error

from qrecauda.dominio.errores import EntradaInvalida, FuenteNoDisponible


@dataclass(frozen=True, slots=True)
class CanalLectura:
    """Canal de lectura clásico de un qubit. Fila = estado preparado, columna = estado leído."""

    p1_dado_0: float  # p(leer 1 | preparado 0)
    p0_dado_1: float  # p(leer 0 | preparado 1)

    def __post_init__(self) -> None:
        for nombre, p in (("p1_dado_0", self.p1_dado_0), ("p0_dado_1", self.p0_dado_1)):
            if not 0.0 <= p <= 1.0:
                raise EntradaInvalida(f"{nombre} debe estar en [0, 1], llegó {p}")

    def matriz(self) -> NDArray[np.float64]:
        return np.array([[1 - self.p1_dado_0, self.p1_dado_0], [self.p0_dado_1, 1 - self.p0_dado_1]])

    def sesgo_analitico(self) -> float:
        """p(1) - 0.5 al medir un qubit en superposición uniforme (H|0>): (p(1|0) - p(0|1)) / 2."""
        return (self.p1_dado_0 - self.p0_dado_1) / 2


# Niveles SINTÉTICOS (no medidos en hardware). RUIDO_MEDIO es el canal de S.02 (p(1|0)=0.02, p(0|1)=0.08).
RUIDO_BAJO = CanalLectura(p1_dado_0=0.005, p0_dado_1=0.01)
RUIDO_MEDIO = CanalLectura(p1_dado_0=0.02, p0_dado_1=0.08)
RUIDO_ALTO = CanalLectura(p1_dado_0=0.05, p0_dado_1=0.15)
NIVELES: dict[str, CanalLectura] = {"bajo": RUIDO_BAJO, "medio": RUIDO_MEDIO, "alto": RUIDO_ALTO}


def modelo_de_ruido(canal: CanalLectura, *, t1_us: float | None = None, t2_us: float | None = None, tiempo_puerta_ns: float = 50.0) -> Any:
    """`NoiseModel` de Aer con el `ReadoutError` del canal en todos los qubits y, si se dan T1/T2, relajación en H."""
    nm = NoiseModel()
    nm.add_all_qubit_readout_error(ReadoutError(canal.matriz().tolist()))
    if (t1_us is None) != (t2_us is None):
        raise EntradaInvalida("la relajación necesita t1_us y t2_us a la vez")
    if t1_us is not None and t2_us is not None:
        if t1_us <= 0 or t2_us <= 0 or t2_us > 2 * t1_us:
            raise EntradaInvalida(f"T1/T2 físicamente imposibles: T1={t1_us} us, T2={t2_us} us (se exige 0 < T2 <= 2·T1)")
        err = thermal_relaxation_error(t1_us * 1e3, t2_us * 1e3, tiempo_puerta_ns)
        nm.add_all_qubit_quantum_error(err, ["h"])
    return nm


def modelo_realista() -> Any:
    """`NoiseModel.from_backend` sobre FakeSherbrooke (`qiskit_ibm_runtime.fake_provider`, calibración congelada: sin red)."""
    try:
        from qiskit_ibm_runtime.fake_provider import FakeSherbrooke
    except ImportError as e:
        raise FuenteNoDisponible(f"el nivel realista necesita qiskit_ibm_runtime.fake_provider: {e}") from e
    return NoiseModel.from_backend(FakeSherbrooke())
