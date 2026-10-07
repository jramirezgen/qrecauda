"""Declaración de una eureka (declaraciones/*.toml, ya fusionada con PARAMETROS.toml): lo único de donde salen semillas y umbrales."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from qrecauda.dominio.errores import EntradaInvalida


@dataclass(frozen=True, slots=True)
class Declaracion:
    eureka: str  # «E2»…
    nodo_corrida: str  # «C.E2»: el id con que la corrida se guarda y se cita
    semillas: tuple[int, ...]
    qubits: int
    shots: int
    tablas: Mapping[str, Mapping[str, object]]  # el TOML fusionado, tabla por tabla
    rutas: tuple[str, ...]  # ficheros que la fijan (declaración, herencias, preinscripción), relativos a la raíz del repo

    def tabla(self, nombre: str) -> Mapping[str, object]:
        if nombre not in self.tablas:
            raise EntradaInvalida(f"la declaración de {self.eureka} no tiene la tabla [{nombre}]")
        return self.tablas[nombre]

    def numero(self, tabla: str, clave: str) -> float:
        v = self.tabla(tabla).get(clave)
        if isinstance(v, bool) or not isinstance(v, int | float):
            raise EntradaInvalida(f"[{tabla}].{clave} de {self.eureka} debe ser un número, no {v!r}")
        return float(v)

    def lista(self, tabla: str, clave: str) -> tuple[str, ...]:
        v = self.tabla(tabla).get(clave)
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            raise EntradaInvalida(f"[{tabla}].{clave} de {self.eureka} debe ser una lista de textos")
        return tuple(v)

    @classmethod
    def desde_mapa(cls, mapa: Mapping[str, object], rutas: tuple[str, ...]) -> Declaracion:
        tablas = {k: v for k, v in mapa.items() if isinstance(v, Mapping)}
        try:
            exp, cad = tablas["experimento"], tablas["cadena"]
            semillas = tuple(int(x) for x in cad["semillas"])
            return cls(str(exp["id"]), str(exp["nodo_corrida"]), semillas, int(cad["qubits"]), int(cad["shots"]), tablas, rutas)
        except (KeyError, ValueError, TypeError) as exc:
            raise EntradaInvalida(f"declaración malformada (¿falta [experimento] o [cadena]?): {exc!r}") from exc
