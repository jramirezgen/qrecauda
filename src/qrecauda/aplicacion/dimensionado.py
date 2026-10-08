"""F5.05: los estimadores del dimensionado conservador, armados en UN sitio para quien los necesite (E5, la demo, la reserva).

«mcv» es el pipeline de 0.1.0: sin un solo argumento nuevo. «conservador» dimensiona sobre el MÍNIMO de la cota MCV y el 90B del pool
y limita además por la contabilidad de la muestra cruda (`h_contable`). Sólo conoce puertos y dominio (C1/C3): el 90B llega inyectado.
"""

from __future__ import annotations

from dataclasses import dataclass

from qrecauda.dominio.entropia import EstimadorMCV, EstimadorMinimo, EstimadorPorVistas
from qrecauda.dominio.errores import EntradaInvalida
from qrecauda.puertos import EstimadorDeEntropia


@dataclass(frozen=True, slots=True)
class EstimadoresConservadores:
    minimo: EstimadorMinimo  # `estimador` del pipeline: min(MCV, 90B sobre el prefijo del pool)
    de_salida: EstimadorDeEntropia  # M2 de la clave: el 90B no puede (la clave queda bajo 10⁶ bits)
    de_fuente: EstimadorDeEntropia  # sobre la muestra que entra a Peres, para la contabilidad `h_contable`

    def kw_del_pipeline(self) -> dict[str, EstimadorDeEntropia]:
        return {"estimador": self.minimo, "estimador_de_salida": self.de_salida, "estimador_de_fuente": self.de_fuente}


def estimadores_conservadores(estimador_90b: EstimadorDeEntropia, prefijo: int, *, qubits: int | None = None) -> EstimadoresConservadores:
    """Los tres estimadores del dimensionado conservador, tal como los cablea `EjecutorE5`.

    `qubits=None` reproduce EXACTAMENTE lo medido en E5 (90B sobre el prefijo qubit-mayor de la muestra cruda). Con `qubits`, la cota de la
    fuente es el mínimo de varias vistas (`EstimadorPorVistas`): opción más estricta, que no cambia lo ya medido."""
    if prefijo < 1:
        raise EntradaInvalida(f"el prefijo del 90B debe ser positivo, llegó {prefijo}")
    cota_fuente: EstimadorDeEntropia = estimador_90b if qubits is None else EstimadorPorVistas(estimador_90b, qubits, prefijo)
    return EstimadoresConservadores(
        EstimadorMinimo([(EstimadorMCV(), None), (estimador_90b, prefijo)]),
        EstimadorMCV(),
        EstimadorMinimo([(cota_fuente, prefijo if qubits is None else None)]),
    )
