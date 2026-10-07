"""`RuidoDeLectura`: qué ruido de lectura pide un experimento, sin saber qué SDK lo fabrica (lo resuelve el laboratorio)."""

from __future__ import annotations

from dataclasses import dataclass

from qrecauda.dominio.errores import EntradaInvalida


@dataclass(frozen=True, slots=True)
class RuidoDeLectura:
    """`canal` = (p(1|0), p(0|1)) sintético; sin canal y sin `realista` = ningún ruido inyectado; `realista` = backend falso congelado."""

    nombre: str  # «bajo» | «medio» | «alto» | «realista» | «sin_ruido» | «simetrico»
    canal: tuple[float, float] | None = None
    realista: bool = False

    def __post_init__(self) -> None:
        if self.canal is not None:
            if self.realista:
                raise EntradaInvalida(f"{self.nombre}: o un canal sintético o el realista, no ambos")
            if not all(0.0 <= p <= 1.0 for p in self.canal):
                raise EntradaInvalida(f"{self.nombre}: las probabilidades del canal deben estar en [0, 1], llegó {self.canal}")

    def sesgo_analitico(self) -> float:
        """|p(1) − ½| esperado de H|0> a través del canal: |p(1|0) − p(0|1)| / 2. Sólo existe si hay canal sintético."""
        if self.canal is None:
            raise EntradaInvalida(f"{self.nombre}: sin canal sintético no hay sesgo analítico")
        return abs(self.canal[0] - self.canal[1]) / 2
