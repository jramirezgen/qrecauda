"""EstimadorDeSesgo — ZNE y PEC sobre el observable de sesgo ⟨Z⟩ (DAG F4.02; decisiones D-003 y D-009, spike S.02).

⟨Z⟩ = 1 − 2·p1, promediado sobre los qubits de H^⊗n. Ideal: 0. Un sesgo de bit |p1 − 1/2| es |⟨Z⟩|/2.

ZNE y PEC se definen sobre VALORES ESPERADOS, no sobre bitstrings (D-003): aquí devuelven una estimación (`float`) y un
`ReporteSesgo` con ⟨Z⟩ sin mitigar y mitigado. No implementan `Mitigador` y no producen bits.

Dónde tienen sentido (D-009):
- Ruido de PUERTA no unitario sobre H (relajación T1/T2): desplaza ⟨Z⟩ de 0 a 1 − e^(−t/T1). El plegado de puertas lo escala
  (ZNE) y su inversa de cuasi-probabilidad lo cancela (PEC).
- Ruido de LECTURA: el plegado de puertas no lo toca y el perfil de puerta no lo contiene, así que NO se espera efecto. Se
  declara `Efecto.SIN_EFECTO_ESPERADO` (ZNE: por los datos, comparando factores; PEC: por perfil de puerta trivial) y la
  corrida de puerta está en `tests/adaptadores/test_zne_pec.py`. Para lectura, el puerto es `Mitigador` (F4.01).

Cómo funcionan:
- ZNE: pliega cada H en H·(H·H)^k (factor de plegado λ = 1 + 2k; H es autoinversa) y extrapola ⟨Z⟩ a ruido de puerta cero
  (Richardson o recta de mínimos cuadrados).
  ESCALA DE RUIDO: el plegado NO escala el ruido como λ para este observable. A primer orden, el ruido que inyecta cada H sólo
  llega a ⟨Z⟩ si tras él quedan un número PAR de H (cada H intercambia Z↔X), es decir (λ+1)/2 de las λ puertas. Por eso la
  variable de extrapolación es la escala efectiva s = (λ+1)/2 y el cero ideal está en s = 0 (λ = −1), no en λ = 0. Extrapolar a
  λ = 0 (`escala="ingenua"`) deja la mitad del sesgo (lo comprueba `test_zne_escala_ingenua_deja_la_mitad`). ⚠️ s(λ) está
  deducida a primer orden en el ruido y contrastada con Aer sólo para este circuito (H^⊗n, relajación en la H); no vale para
  otros circuitos ni para otro ruido sin rederivarla.
- PEC: con la matriz de transferencia de Pauli (PTM) del canal de relajación, su inversa se descompone en {I, X, Y, Z,
  reset|0>, reset|1>} con coeficientes q_k (Σq_k = 1, γ = Σ|q_k| > 1). Cada circuito muestrea una operación por qubit con
  probabilidad |q_k|/γ y pondera con signo·γ. Cada qubit se estima con su propio signo (el observable es de un solo qubit).

Alcance declarado (honesto):
- ⚠️ sin verificar: PNA (propagated noise absorption) y `Samplomatic` NO se implementan. Samplomatic 0.21.0 está instalado pero
  PNA exige un modelo de ruido Pauli-Lindblad aprendido (NoiseLearner) en el servicio de IBM; no hay forma de correrlo en Aer
  local, y no se simula como si lo fuera. PEC aquí es PEC con perfil de ruido CONOCIDO, no aprendido.
- ⚠️ sin verificar en hardware: todo lo de aquí corre en AerSimulator con ruido sintético. En hardware real el perfil no se conoce
  exacto y las operaciones base también tienen ruido; PEC supone operaciones base ideales (X, Y, Z y reset sin error).
- El ruido entra por parámetro (`noise_model` y, para PEC, `RelajacionConocida`); este módulo no importa a `aer` (C2).
- Relajación modelada con población excitada nula (la de `thermal_relaxation_error` por defecto).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal

import numpy as np
import qiskit_aer
from numpy.typing import NDArray
from qiskit import QuantumCircuit
from qiskit.exceptions import QiskitError
from qiskit_aer import AerSimulator

from qrecauda.dominio.errores import EntradaInvalida, FuenteNoDisponible
from qrecauda.dominio.muestra import Muestra, Origen

Extrapolacion = Literal["richardson", "lineal"]
Escala = Literal["efectiva", "ingenua"]


class Tecnica(StrEnum):
    ZNE = "zne"
    PEC = "pec"


class Efecto(StrEnum):
    CORRIGE = "corrige"
    SIN_EFECTO_ESPERADO = "sin_efecto_esperado"  # el ruido presente no es el que esta técnica actúa sobre


@dataclass(frozen=True, slots=True)
class ReporteSesgo:
    """⟨Z⟩ con y sin mitigar de una misma fuente, más lo necesario para leerlo sin fiarse del titular."""

    tecnica: Tecnica
    z_crudo: float  # de la muestra recibida
    z_mitigado: float
    error_estandar: float  # del z_mitigado (propaga la amplificación de la extrapolación o γ)
    efecto: Efecto
    valores_por_factor: tuple[tuple[int, float], ...] = ()  # ZNE: (λ, ⟨Z⟩(λ))
    gamma: float | None = None  # PEC: coste de muestreo γ = Σ|q_k|


@dataclass(frozen=True, slots=True)
class RelajacionConocida:
    """Perfil de relajación de la puerta H que PEC invierte. Mismas unidades que `modelo_de_ruido` de `aer.ruido`."""

    t1_us: float
    t2_us: float
    tiempo_puerta_ns: float

    def __post_init__(self) -> None:
        if self.t1_us <= 0 or self.t2_us <= 0 or self.tiempo_puerta_ns <= 0:
            raise EntradaInvalida("T1, T2 y el tiempo de puerta deben ser positivos")
        if self.t2_us > 2 * self.t1_us:
            raise EntradaInvalida(f"T1/T2 físicamente imposibles: T1={self.t1_us} us, T2={self.t2_us} us (se exige T2 <= 2·T1)")

    @property
    def a(self) -> float:
        """Factor que el canal aplica a ⟨X⟩ y ⟨Y⟩: e^(−t/T2)."""
        return math.exp(-self.tiempo_puerta_ns / (self.t2_us * 1e3))

    @property
    def b(self) -> float:
        """Factor que el canal aplica a ⟨Z⟩: e^(−t/T1). El canal además lleva I → Z con peso 1 − b."""
        return math.exp(-self.tiempo_puerta_ns / (self.t1_us * 1e3))


_OPERACIONES = ("I", "X", "Y", "Z", "R0", "R1")


def descomposicion_inversa(perfil: RelajacionConocida | None) -> dict[str, float]:
    """Coeficientes q_k de Λ⁻¹ = Σ q_k·B_k en {I, X, Y, Z, reset|0>, reset|1>}. `None` = canal trivial: q_I = 1.

    PTM del canal sobre (I, X, Y, Z): diag(1, a, a, b) con la entrada (Z, I) = 1 − b. Su inversa es diag(1, 1/a, 1/a, 1/b) con
    (Z, I) = −(1 − b)/b. La parte diagonal sale de la transformada de Hadamard sobre los signos de conjugación de Pauli; la
    entrada (Z, I) la aportan reset|0> y reset|1> (PTM = E_II ± E_ZI) con coeficientes ±c/2, cuyas diagonales se cancelan.
    """
    if perfil is None:
        return {"I": 1.0, "X": 0.0, "Y": 0.0, "Z": 0.0, "R0": 0.0, "R1": 0.0}
    a, b = perfil.a, perfil.b
    d = (1.0, 1.0 / a, 1.0 / a, 1.0 / b)
    c = -(1.0 - b) / b
    return {
        "I": (d[0] + d[1] + d[2] + d[3]) / 4,
        "X": (d[0] + d[1] - d[2] - d[3]) / 4,
        "Y": (d[0] - d[1] + d[2] - d[3]) / 4,
        "Z": (d[0] - d[1] - d[2] + d[3]) / 4,
        "R0": c / 2,
        "R1": -c / 2,
    }


def _validar_muestra(muestra: Muestra) -> None:
    if muestra.mitigada:
        raise EntradaInvalida("la muestra ya está mitigada: el ⟨Z⟩ sin mitigar tiene que venir de una muestra cruda")
    if muestra.origen is not Origen.SIMULADOR_AER:
        raise EntradaInvalida(f"no se puede re-ejecutar una muestra de origen {muestra.origen.value}: ZNE/PEC vuelven a medir")


def _z_crudo(muestra: Muestra) -> float:
    return 1.0 - 2.0 * muestra.bits.proporcion_de_unos()


def _simulador(noise_model: Any | None) -> AerSimulator:
    # fusion_enable=False: Aer no debe fundir las H plegadas en una sola puerta (anularía el ruido añadido por el plegado)
    return AerSimulator(noise_model=noise_model, fusion_enable=False) if noise_model is not None else AerSimulator(fusion_enable=False)


def _bits_por_disparo(memoria: list[str], n: int) -> NDArray[np.uint8]:
    """(disparos, n): columna q = clbit q. Cada cadena de Aer es big-endian (el carácter 0 es el clbit n−1)."""
    planas = np.frombuffer("".join(s.replace(" ", "") for s in memoria).encode("ascii"), dtype=np.uint8) - ord("0")
    return np.ascontiguousarray(planas.reshape(len(memoria), n)[:, ::-1])


def _ejecutar(circuito: QuantumCircuit, simulador: AerSimulator, shots: int, semilla: int | None) -> NDArray[np.uint8]:
    opciones: dict[str, Any] = {"shots": shots, "memory": True}
    if semilla is not None:
        opciones["seed_simulator"] = semilla
    try:
        memoria = simulador.run(circuito, **opciones).result().get_memory()
    except (QiskitError, ValueError, TypeError, KeyError, AttributeError) as e:
        raise FuenteNoDisponible(f"AerSimulator no pudo ejecutar el circuito: {e}") from e
    return _bits_por_disparo(memoria, circuito.num_qubits)


def _pesos_extrapolacion(escalas: tuple[float, ...], metodo: Extrapolacion) -> NDArray[np.float64]:
    """Pesos w tales que ⟨Z⟩(s = 0) = Σ w_i·⟨Z⟩(s_i)."""
    x = np.array(escalas, dtype=np.float64)
    if metodo == "richardson":
        return np.array([np.prod([(0.0 - xj) / (xi - xj) for j, xj in enumerate(x) if j != i]) for i, xi in enumerate(x)])
    media = x.mean()
    return 1.0 / len(x) - media * (x - media) / float(((x - media) ** 2).sum())


class ZneSobreZ:
    """Implementa `EstimadorDeSesgo` con ZNE por plegado de puertas (H → H·H·H …). Determinista dada `semilla`.

    `estimar` devuelve ⟨Z⟩ extrapolado a ruido de puerta cero; `reportar` devuelve además el crudo, los ⟨Z⟩(λ) y el veredicto.
    """

    def __init__(
        self,
        noise_model: Any | None,
        semilla: int | None = None,
        factores: tuple[int, ...] = (1, 3, 5),
        extrapolacion: Extrapolacion = "richardson",
        escala: Escala = "efectiva",
    ) -> None:
        if len(factores) < 2 or len(set(factores)) != len(factores) or any(f < 1 or f % 2 == 0 for f in factores):
            raise EntradaInvalida(f"los factores de plegado son enteros impares, positivos y distintos (al menos dos): {factores}")
        if extrapolacion not in ("richardson", "lineal"):
            raise EntradaInvalida(f"extrapolación desconocida: {extrapolacion!r}")
        if escala not in ("efectiva", "ingenua"):
            raise EntradaInvalida(f"escala desconocida: {escala!r}")
        self._escala: Escala = escala
        self._noise_model = noise_model
        self._semilla = semilla
        self._factores = tuple(sorted(factores))
        self._extrapolacion: Extrapolacion = extrapolacion

    def estimar(self, muestra: Muestra) -> float:
        return self.reportar(muestra).z_mitigado

    def reportar(self, muestra: Muestra) -> ReporteSesgo:
        _validar_muestra(muestra)
        n = muestra.qubits
        rng = np.random.default_rng(self._semilla)
        sim = _simulador(self._noise_model)
        valores: list[float] = []
        errores: list[float] = []
        for lam in self._factores:
            qc = QuantumCircuit(n)
            for q in range(n):
                qc.h(q)
                for _ in range((lam - 1) // 2):
                    qc.barrier(q)
                    qc.h(q)
                    qc.barrier(q)
                    qc.h(q)
            qc.measure_all()
            semilla = None if self._semilla is None else int(rng.integers(0, 2**31 - 1))
            z = 1.0 - 2.0 * _ejecutar(qc, sim, muestra.shots, semilla).astype(np.float64)
            valores.append(float(z.mean()))
            errores.append(float(z.std(ddof=1) / math.sqrt(z.size)))
        escalas = tuple((lam + 1) / 2 if self._escala == "efectiva" else float(lam) for lam in self._factores)
        w = _pesos_extrapolacion(escalas, self._extrapolacion)
        z_mit = float(w @ np.array(valores))
        se = float(np.sqrt(((w * np.array(errores)) ** 2).sum()))
        # veredicto por los DATOS: si el ruido no escala con el plegado, ZNE no tiene nada que extrapolar
        salto = abs(valores[-1] - valores[0])
        efecto = Efecto.CORRIGE if salto > 3.0 * math.hypot(errores[0], errores[-1]) else Efecto.SIN_EFECTO_ESPERADO
        return ReporteSesgo(Tecnica.ZNE, _z_crudo(muestra), z_mit, se, efecto, tuple(zip(self._factores, valores, strict=True)))


class PecSobreZ:
    """Implementa `EstimadorDeSesgo` con PEC sobre ⟨Z⟩ para un perfil de relajación de puerta CONOCIDO. Determinista dada `semilla`.

    `perfil=None` declara que no hay ruido de puerta que invertir (p. ej. sólo lectura): γ = 1, sin efecto esperado.
    `circuitos` es el número de circuitos muestreados; los disparos de la muestra se reparten entre ellos.
    """

    def __init__(
        self, noise_model: Any | None, perfil: RelajacionConocida | None, semilla: int | None = None, circuitos: int = 400
    ) -> None:
        if circuitos < 1:
            raise EntradaInvalida(f"circuitos debe ser positivo, llegó {circuitos}")
        self._noise_model = noise_model
        self._perfil = perfil
        self._semilla = semilla
        self._circuitos = circuitos

    def estimar(self, muestra: Muestra) -> float:
        return self.reportar(muestra).z_mitigado

    def reportar(self, muestra: Muestra) -> ReporteSesgo:
        _validar_muestra(muestra)
        n = muestra.qubits
        q = descomposicion_inversa(self._perfil)
        gamma = sum(abs(v) for v in q.values())
        probs = np.array([abs(q[k]) for k in _OPERACIONES]) / gamma
        signos = np.array([1.0 if q[k] >= 0 else -1.0 for k in _OPERACIONES])
        rng = np.random.default_rng(self._semilla)
        circuitos = min(self._circuitos, muestra.shots)
        por_circuito = muestra.shots // circuitos
        sim = _simulador(self._noise_model)
        estimas = np.empty(circuitos)
        for c in range(circuitos):
            ops = rng.choice(len(_OPERACIONES), size=n, p=probs)
            qc = QuantumCircuit(n)
            for qb in range(n):
                qc.h(qb)
                self._aplicar(qc, qb, _OPERACIONES[int(ops[qb])])
            qc.measure_all()
            semilla = None if self._semilla is None else int(rng.integers(0, 2**31 - 1))
            z_qubit = (1.0 - 2.0 * _ejecutar(qc, sim, por_circuito, semilla).astype(np.float64)).mean(axis=0)
            estimas[c] = float((gamma * signos[ops] * z_qubit).mean())
        z_mit = float(estimas.mean())
        se = float(estimas.std(ddof=1) / math.sqrt(circuitos)) if circuitos > 1 else float("nan")
        efecto = Efecto.SIN_EFECTO_ESPERADO if self._perfil is None else Efecto.CORRIGE
        return ReporteSesgo(Tecnica.PEC, _z_crudo(muestra), z_mit, se, efecto, gamma=gamma)

    @staticmethod
    def _aplicar(qc: QuantumCircuit, qubit: int, op: str) -> None:
        if op == "X":
            qc.x(qubit)
        elif op == "Y":
            qc.y(qubit)
        elif op == "Z":
            qc.z(qubit)
        elif op in ("R0", "R1"):
            qc.reset(qubit)
            if op == "R1":
                qc.x(qubit)


__all__ = ["Efecto", "PecSobreZ", "RelajacionConocida", "ReporteSesgo", "Tecnica", "ZneSobreZ", "descomposicion_inversa", "qiskit_aer"]
