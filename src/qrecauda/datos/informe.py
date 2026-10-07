"""`InformeCorrida`: el artefacto que cada corrida escribe en registro/corridas/. Tipado, versionado y validado al leer."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from qrecauda.dominio.errores import EntradaInvalida, EsquemaFuturo
from qrecauda.dominio.metricas import Medida, Metrica, Veredicto
from qrecauda.dominio.muestra import Origen

ESQUEMA_INFORME = 1


@dataclass(frozen=True, slots=True)
class InformeCorrida:
    corrida: str  # id del nodo del DAG (p. ej. «E1b»)
    origen: Origen
    qubits: int
    shots: int
    mitigada: bool
    h_min_entrada: float  # decide la longitud segura
    bits_crudos: int
    bits_clave: int
    veredicto: Veredicto
    entorno: Mapping[str, str]  # versiones exactas (transversal/reproducibilidad)
    esquema: int = ESQUEMA_INFORME

    def a_mapa(self) -> dict[str, object]:
        return {
            "esquema": self.esquema,
            "corrida": self.corrida,
            "origen": self.origen.value,
            "qubits": self.qubits,
            "shots": self.shots,
            "mitigada": self.mitigada,
            "h_min_entrada": self.h_min_entrada,
            "bits_crudos": self.bits_crudos,
            "bits_clave": self.bits_clave,
            "aprobado": self.veredicto.aprobado,
            "medidas": [[m.metrica.value, m.valor, m.umbral, m.cumple] for m in self.veredicto.medidas],
            "entorno": dict(self.entorno),
        }

    @classmethod
    def desde_mapa(cls, d: Mapping[str, object]) -> InformeCorrida:
        if "esquema" not in d:
            raise EntradaInvalida("el informe no declara `esquema`")
        if int(d["esquema"]) > ESQUEMA_INFORME:  # type: ignore[call-overload]
            raise EsquemaFuturo(f"esquema {d['esquema']} > {ESQUEMA_INFORME}: actualiza qrecauda")
        try:
            medidas = tuple(Medida(Metrica(m[0]), float(m[1]), float(m[2]), bool(m[3])) for m in d["medidas"])  # type: ignore[attr-defined]
            return cls(
                corrida=str(d["corrida"]),
                origen=Origen(str(d["origen"])),
                qubits=int(d["qubits"]),  # type: ignore[call-overload]
                shots=int(d["shots"]),  # type: ignore[call-overload]
                mitigada=bool(d["mitigada"]),
                h_min_entrada=float(d["h_min_entrada"]),  # type: ignore[arg-type]
                bits_crudos=int(d["bits_crudos"]),  # type: ignore[call-overload]
                bits_clave=int(d["bits_clave"]),  # type: ignore[call-overload]
                veredicto=Veredicto(medidas),
                entorno=dict(d["entorno"]),  # type: ignore[call-overload]
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise EntradaInvalida(f"informe malformado: {exc}") from exc
