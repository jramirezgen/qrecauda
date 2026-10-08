"""R.02: los estimadores del dimensionado conservador, armados en un solo sitio. Sin binarios ni Aer."""

from __future__ import annotations

from qrecauda.aplicacion.dimensionado import estimadores_conservadores
from qrecauda.dominio.bits import Bits
from qrecauda.dominio.entropia import EstimadorMCV, EstimadorMinimo, EstimadorPorVistas


class _Noventa:
    def __init__(self) -> None:
        self.vistos: list[int] = []

    def estimar(self, bits: Bits) -> float:
        self.vistos.append(len(bits))
        return 0.5


def test_sin_qubits_es_exactamente_el_cableado_de_e5() -> None:
    """Lo medido en E5 (`conservador`): MCV y 90B-sobre-prefijo para el pool, MCV para la clave, 90B-sobre-prefijo para la fuente."""
    n90 = _Noventa()
    e = estimadores_conservadores(n90, 100)
    assert isinstance(e.minimo, EstimadorMinimo) and isinstance(e.de_salida, EstimadorMCV)
    bits = Bits.desde([0, 1] * 200)
    assert e.minimo.por_cota(bits)[1] == 0.5 and e.de_fuente.estimar(bits) == 0.5
    assert n90.vistos == [100, 100]  # los dos 90B (pool y fuente) ven el prefijo, no la muestra entera


def test_con_qubits_la_fuente_se_mira_por_vistas_y_el_pool_igual() -> None:
    n90 = _Noventa()
    e = estimadores_conservadores(n90, 100, qubits=4)
    assert set(e.kw_del_pipeline()) == {"estimador", "estimador_de_salida", "estimador_de_fuente"}
    bits = Bits.desde([0, 1] * 200)  # 400 bits: 4 qubits × 100 disparos ⇒ prefijo, intercalado y 4 columnas
    e.de_fuente.estimar(bits)
    assert len(n90.vistos) == 6 and isinstance(e.de_fuente._cotas[0][0], EstimadorPorVistas)  # type: ignore[attr-defined]
