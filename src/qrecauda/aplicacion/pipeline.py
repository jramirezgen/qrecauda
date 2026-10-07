"""Orquestador: fuente → (mitigación) → von Neumann/Peres → Toeplitz → validación → clave.

Las medidas M1, M3, M4, M5 se toman en TRES puntos (muestra cruda, mitigada, clave): medir sólo la clave haría que cualquier
fuente pasase, porque Toeplitz limpia lo que el ruido ensució (hallazgo R.00-1).

Es la bala trazadora: corre de punta a punta con cualquier `FuenteDeBits` (PRNG clásico hoy, Aer o IBM después).
"""

from __future__ import annotations

from dataclasses import dataclass

from qrecauda.dominio.bits import Bits
from qrecauda.dominio.entropia import EstimadorMCV
from qrecauda.dominio.errores import EntropiaInsuficiente
from qrecauda.dominio.extractores import longitud_segura, peres, toeplitz
from qrecauda.dominio.metricas import Medida, Metrica, Veredicto, medir
from qrecauda.dominio.muestra import Muestra
from qrecauda.puertos import EstimadorDeEntropia, FuenteDeBits, Mitigador, Reloj, Validador


@dataclass(frozen=True, slots=True)
class ParametrosPipeline:
    qubits: int
    shots: int
    epsilon: float = 2.0**-64  # parámetro de seguridad del LHL
    profundidad_peres: int = 8


@dataclass(frozen=True, slots=True)
class Resultado:
    clave: Bits
    muestra: Muestra
    h_min: float  # min-entropía de ENTRADA al extractor: decide la longitud segura
    h_min_salida: float  # min-entropía de la clave (M2): ≈ 1 por construcción, no basta como prueba
    veredicto: Veredicto  # sobre la clave
    etapas: tuple[tuple[str, tuple[Medida, ...]], ...]  # ("cruda" | "mitigada" | "clave", M1/M3/M4/M5)
    bits_crudos: int
    bits_extraidos: int
    segundos: float

    def medidas_de(self, etapa: str) -> tuple[Medida, ...]:
        return dict(self.etapas)[etapa]


def ejecutar(
    fuente: FuenteDeBits,
    validador: Validador,
    reloj: Reloj,
    p: ParametrosPipeline,
    mitigador: Mitigador | None = None,
    estimador: EstimadorDeEntropia | None = None,
) -> Resultado:
    est = estimador if estimador is not None else EstimadorMCV()
    t0 = reloj.ahora_ns()
    muestra = fuente.generar(p.qubits, p.shots)
    etapas = [("cruda", validador.evaluar(muestra.bits))]
    if mitigador is not None:
        muestra = mitigador.mitigar(muestra)
        etapas.append(("mitigada", validador.evaluar(muestra.bits)))
    pool = peres(muestra.bits, p.profundidad_peres)
    h = est.estimar(pool)
    # n·(2+h) ≤ |pool|: caben n bits de datos y la semilla de n+m−1 ≤ n·(1+h) bits, ambas del mismo pool.
    n = int((len(pool) + 1) // (2 + h))
    if n < 2:
        raise EntropiaInsuficiente(f"pool de {len(pool)} bits con h_min={h:.4f}: no alcanza para datos y semilla")
    m = longitud_segura(n, h, p.epsilon)
    datos, semilla = pool[:n], pool[n : n + n + m - 1]
    clave = toeplitz(datos, semilla, m)
    dt = (reloj.ahora_ns() - t0) / 1e9
    h_salida = est.estimar(clave)
    en_clave = validador.evaluar(clave)
    etapas.append(("clave", en_clave))
    medidas: tuple[Medida, ...] = (
        *en_clave,
        medir(Metrica.MIN_ENTROPIA, h_salida),
        medir(Metrica.TASA, len(clave) / dt if dt > 0 else float("inf")),
        medir(Metrica.LATENCIA, dt * 1000),
    )
    return Resultado(clave, muestra, h, h_salida, Veredicto(medidas), tuple(etapas), len(muestra.bits), len(pool), dt)
