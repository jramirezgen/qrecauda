"""Cotas de entropía. Estas son estimaciones conservadoras de dominio; la batería completa de NIST SP 800-90B
es un adaptador (adaptadores/nist) y se contrasta con esta en un contract test."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Protocol

from .bits import Bits
from .errores import EntradaInvalida

Z_99 = 2.5758293035489004  # cuantil 0,995 de la normal: cota superior al 99 % (NIST SP 800-90B §6.3.1)


def sesgo(bits: Bits) -> float:
    """|p(1) − 1/2|: lo que la métrica M1 («sesgo de lectura») compara con su umbral."""
    return abs(bits.proporcion_de_unos() - 0.5)


def min_entropia_mcv(bits: Bits) -> float:
    """Most Common Value: H_min = −log2(p_u), con p_u la cota superior al 99 % de la frecuencia del símbolo más común."""
    n = len(bits)
    if n < 2:
        raise EntradaInvalida("la min-entropía necesita al menos 2 bits")
    p_hat = max(bits.proporcion_de_unos(), 1 - bits.proporcion_de_unos())
    p_u = min(1.0, p_hat + Z_99 * math.sqrt(p_hat * (1 - p_hat) / (n - 1)))
    return -math.log2(p_u)


class EstimadorMCV:
    """Implementa `EstimadorDeEntropia` con la cota MCV. ⚠️ Es ciega a la dependencia entre bits (S.04, hallazgo R.00-2):
    sirve para fuentes IID; contra una cadena de Markov la sobreestima. El pipeline acepta otro estimador por el puerto."""

    def estimar(self, bits: Bits) -> float:
        return min_entropia_mcv(bits)


class CotaDeEntropia(Protocol):
    """Lo único que `EstimadorMinimo` pide a cada cota: la misma firma que el puerto `EstimadorDeEntropia`, que el dominio no importa."""

    def estimar(self, bits: Bits) -> float: ...


class EstimadorMinimo:
    """Dimensionado conservador (F5.05): `h = min` de varias cotas, cada una sobre a lo sumo `tope` primeros bits (`None` = todos).

    El 90B exige ≥ 10⁶ muestras y cuesta segundos: se le da un prefijo fijo. ⚠️ Un prefijo del pool de Peres no es muestra
    representativa (el pool empieza por la parte von Neumann y sigue con el reciclado); por eso la contabilidad de `h_contable`
    es la segunda cota, no un adorno. Si alguna cota no puede evaluarse (muestra corta), su error se propaga: no se ignora en silencio.
    """

    def __init__(self, cotas: Sequence[tuple[CotaDeEntropia, int | None]]) -> None:
        if not cotas:
            raise ValueError("EstimadorMinimo necesita al menos una cota")
        self._cotas = tuple(cotas)

    def por_cota(self, bits: Bits) -> tuple[float, ...]:
        return tuple(c.estimar(bits if tope is None else bits[:tope]) for c, tope in self._cotas)

    def estimar(self, bits: Bits) -> float:
        return min(self.por_cota(bits))


class EstimadorPorVistas:
    """Cota sobre la MUESTRA CRUDA que no depende de qué qubits caen en el prefijo (R.02, hallazgo del 90B qubit-mayor).

    La muestra de `FuenteAer`/`FuenteIbm` va en orden QUBIT-MAYOR (todos los disparos del qubit 0, luego los del 1…), así que el prefijo de
    10⁶ bits que se le da al 90B puede cubrir sólo los primeros qubits y no ver al peor ni la dependencia ENTRE qubits. Aquí la cota es el
    mínimo de varias vistas de los mismos bits, cada una sobre a lo sumo `prefijo` bits: (1) el prefijo qubit-mayor de siempre; (2) el
    INTERCALADO por disparo (disparo 0 de todos los qubits, disparo 1…), que reparte el prefijo entre todos los qubits y deja ver la
    correlación entre ellos; (3) cada COLUMNA de qubit, sólo si tiene al menos `prefijo` disparos (el 90B no admite menos: no se inventa).
    Es OPCIONAL: lo medido en E1–E5 usa el prefijo solo."""

    def __init__(self, interior: CotaDeEntropia, qubits: int, prefijo: int) -> None:
        if qubits < 1 or prefijo < 1:
            raise EntradaInvalida(f"qubits y prefijo deben ser positivos, llegó {qubits}, {prefijo}")
        self._interior, self._qubits, self._prefijo = interior, qubits, prefijo

    def por_vista(self, bits: Bits) -> dict[str, float]:
        q, n = self._qubits, len(bits)
        if n % q:
            raise EntradaInvalida(f"{n} bits no son una muestra qubit-mayor de {q} qubits")
        disparos = n // q
        m = bits.datos.reshape(q, disparos)
        vistas: dict[str, Bits] = {"qubit-mayor": bits[: self._prefijo]}
        if q > 1:
            vistas["por-disparo"] = Bits(m.T.reshape(-1)[: self._prefijo])
        if disparos >= self._prefijo:
            vistas.update({f"columna-{k}": Bits(m[k, : self._prefijo]) for k in range(q)})
        return {nombre: self._interior.estimar(v) for nombre, v in vistas.items()}

    def estimar(self, bits: Bits) -> float:
        return min(self.por_vista(bits).values())


def h_contable(h_pool: float, bits_pool: int, h_fuente: float, bits_fuente: int) -> float:
    """Contabilidad de entropía: Peres es una función determinista de la muestra, no crea entropía, así que el pool entero
    no puede tener más que la muestra: `|pool|·h ≤ N·h_fuente`. Devuelve `min(h_pool, h_fuente·N/|pool|)`, por bit de pool.

    Motivo medido (diagnóstico previo a E5, PRNG con persistencia de Markov 0,9 y 3,2 M de bits): el 90B sobre el pool da ≈ 0,65 sea
    cual sea la persistencia, porque Peres reparte la dependencia por el pool; sobre la muestra cruda sí la ve (0,037)."""
    if bits_pool < 1 or bits_fuente < 1:
        raise ValueError("la contabilidad necesita pool y muestra no vacíos")
    return min(h_pool, h_fuente * bits_fuente / bits_pool)


def h_min_con_defecto(peso: float, p_fresca_max: float) -> float:
    """Min-entropía por bit (analítica) de una fuente con un defecto de peso `peso` sobre bits frescos de P(1 | 0) ≤ `p_fresca_max`.

    Sirve a las dos formas de E5: con probabilidad `peso` el bit COPIA al anterior (cadena de Markov con persistencia) o toma el valor
    de un patrón fijo (semidetermista); si no, es un bit fresco. En ambas la secuencia más probable acierta cada bit con
    `peso + (1 − peso)·p_fresca_max`, así que H∞(N bits) = N·h con h = −log2 de eso (± un bit en la cadena de Markov, por el primer
    bit). Con `p_fresca_max` mayor que el sesgo real el techo sale MÁS ESTRICTO, no más laxo."""
    if not 0.0 <= peso <= 1.0 or not 0.5 <= p_fresca_max <= 1.0:
        raise ValueError(f"peso en [0, 1] y p_fresca_max en [½, 1]; llegó {peso}, {p_fresca_max}")
    return -math.log2(peso + (1.0 - peso) * p_fresca_max)
