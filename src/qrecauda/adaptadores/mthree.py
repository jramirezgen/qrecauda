"""Mitigador — twirling de lectura propio (TREX-like) y contraste con mthree (DAG F4.01; decisión D-009, spike S.02).

D-009: mthree devuelve cuasi-probabilidades de conteos, no bitstrings por disparo; un QRNG consume los bits, así que la
técnica que implementa el puerto `Mitigador` es el twirling propio. mthree entra sólo como cifra de contraste
(`sesgo_mthree`), nunca como fuente de bits.

Twirling de lectura: por bloque de disparos y por qubit, una máscara aleatoria decide si se aplica X justo antes de medir;
tras medir, el resultado se XOR-ea con la misma máscara. El estado de H|0> es invariante bajo X, así que la distribución
ideal no cambia, pero el canal de lectura asimétrico queda simetrizado (p efectiva = (p(1|0)+p(0|1))/2) y el sesgo cae.

Alcance declarado (honesto):
- Twirling necesita aplicar X ANTES de medir, de modo que `mitigar` no puede corregir los bits que ya tiene: RE-EJECUTA
  el mismo experimento (H^⊗n + medición, `qubits` y `shots` de la muestra) con twirling. Los bits de la muestra cruda
  se descartan; la muestra devuelta lleva `mitigada=True` y conserva N bits por disparo.
- Sólo sobre AerSimulator (origen `SIMULADOR_AER`): no hay forma de re-ejecutar hardware desde aquí.
- El ruido de lectura se recibe por parámetro (`noise_model`); este adaptador no importa a `aer` (C2).
- ⚠️ sin verificar: efecto sobre estados NO uniformes (ahí el twirling promedia el canal, no lo elimina).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import qiskit_aer
from numpy.typing import NDArray
from qiskit import QuantumCircuit
from qiskit.exceptions import QiskitError
from qiskit_aer import AerSimulator

from qrecauda.dominio.bits import Bits
from qrecauda.dominio.errores import EntradaInvalida, FuenteNoDisponible
from qrecauda.dominio.muestra import Muestra, Origen, Procedencia


def _bloques(shots: int, bloque: int) -> list[int]:
    completos, resto = divmod(shots, bloque)
    return [bloque] * completos + ([resto] if resto else [])


class TwirlingLectura:
    """Implementa `Mitigador` con twirling de lectura propio. Determinista dado `semilla` (máscaras y muestreo de Aer)."""

    def __init__(self, noise_model: Any | None, semilla: int | None = None, bloque: int = 200) -> None:
        if bloque < 1:
            raise EntradaInvalida(f"el bloque debe ser positivo, llegó {bloque}")
        self._noise_model = noise_model
        self._semilla = semilla
        self._bloque = bloque

    def mitigar(self, muestra: Muestra) -> Muestra:
        if muestra.mitigada:
            raise EntradaInvalida("la muestra ya está mitigada: mitigar dos veces no es idempotente ni está definido")
        if muestra.origen is not Origen.SIMULADOR_AER:
            raise EntradaInvalida(f"no se puede re-ejecutar una muestra de origen {muestra.origen.value}: el twirling mide de nuevo")
        qc = QuantumCircuit(muestra.qubits)
        qc.h(range(muestra.qubits))
        qc.measure_all()
        bits = self._muestrear(qc, muestra.shots)
        nueva = muestra.mitigada_con(Bits(bits), conserva_bits_por_disparo=True)
        proc = Procedencia(backend="AerSimulator", version=qiskit_aer.__version__)
        return Muestra(nueva.bits, nueva.origen, nueva.qubits, nueva.shots, True, proc)

    def _muestrear(self, circuito: QuantumCircuit, shots: int) -> NDArray[np.uint8]:
        """Bits QUBIT-MAYOR (como `FuenteAer`) con máscara X por bloque y qubit, deshecha por XOR clásico tras medir."""
        n = circuito.num_qubits
        rng = np.random.default_rng(self._semilla)
        tamanos = _bloques(shots, self._bloque)
        mascaras = rng.integers(0, 2, size=(len(tamanos), n), dtype=np.uint8)
        base = circuito.remove_final_measurements(inplace=False)
        circuitos = []
        for fila in mascaras:
            c = base.copy()
            for q in range(n):
                if fila[q]:
                    c.x(q)
            c.measure_all()
            circuitos.append(c)
        simulador = AerSimulator(noise_model=self._noise_model) if self._noise_model is not None else AerSimulator()
        partes: list[NDArray[np.uint8]] = []
        try:
            for c, tam, fila in zip(circuitos, tamanos, mascaras, strict=True):
                semilla = None if self._semilla is None else int(rng.integers(0, 2**31 - 1))
                opciones: dict[str, Any] = {"shots": tam, "memory": True}
                if semilla is not None:
                    opciones["seed_simulator"] = semilla
                memoria = simulador.run(c, **opciones).result().get_memory()
                # cada cadena es big-endian: el carácter 0 es el clbit n-1
                disparos = np.array([[s.replace(" ", "")[n - 1 - k] == "1" for k in range(n)] for s in memoria], dtype=np.uint8)
                partes.append(disparos ^ fila)  # (tam, n)
        except (QiskitError, ValueError, TypeError, KeyError, AttributeError) as e:
            raise FuenteNoDisponible(f"AerSimulator no pudo muestrear con twirling: {e}") from e
        return np.ascontiguousarray(np.vstack(partes).T).reshape(-1)


def sesgo_mthree(noise_model: Any, *, qubits: int, shots: int, semilla: int) -> tuple[float, float]:
    """CONTRASTE (D-009): sesgo medio por qubit |p1-0.5| de H^⊗n bajo `noise_model`, antes y después de mthree.

    Devuelve cifras, no bits: mthree entrega cuasi-probabilidades. Necesita el extra `mitigacion`.
    """
    if qubits < 1 or shots < 1:
        raise EntradaInvalida(f"qubits y shots deben ser positivos, llegó {qubits}, {shots}")
    try:
        import mthree
    except ImportError as e:
        raise FuenteNoDisponible(f"el contraste necesita el extra «mitigacion» (mthree): {e}") from e
    from qiskit import transpile

    sim = AerSimulator(noise_model=noise_model)
    qc = QuantumCircuit(qubits, qubits)
    qc.h(range(qubits))
    qc.measure(range(qubits), range(qubits))
    tqc = transpile(qc, sim, optimization_level=0)
    mapa = list(mthree.utils.final_measurement_mapping(tqc).keys())
    try:
        cuentas = sim.run(tqc, shots=shots, seed_simulator=semilla).result().get_counts()
        mit = mthree.M3Mitigation(sim)
        mit.cals_from_system(mapa, shots=shots, async_cal=False)
        qp = mit.apply_correction(cuentas, mapa)
    except (QiskitError, ValueError, TypeError, KeyError, AttributeError) as e:
        raise FuenteNoDisponible(f"mthree no pudo calibrar o corregir: {e}") from e

    def p1_por_qubit(dist: dict[str, float]) -> NDArray[np.float64]:
        p1 = np.zeros(qubits)
        total = sum(dist.values())
        for cadena, v in dist.items():
            for q, c in enumerate(reversed(cadena)):
                if c == "1":
                    p1[q] += v / total
        return p1

    antes = float(np.abs(p1_por_qubit({k: float(v) for k, v in cuentas.items()}) - 0.5).mean())
    despues = float(np.abs(p1_por_qubit({k: float(v) for k, v in dict(qp).items()}) - 0.5).mean())
    return antes, despues
