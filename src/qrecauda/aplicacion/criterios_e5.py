"""Los criterios y controles de E5 (docs/preinscripciones/E5.md), como funciones puras sobre lo ya medido.

UNA sola definición: el ejecutor las usa para calcular D5 y P5, y el juez las vuelve a calcular sobre los artefactos releídos.
Los umbrales numéricos viven en `declaraciones/E5.toml` (los de M1–M6, en `dominio.metricas`); aquí no se teclea ninguno.
Un «resultado» es el mapa JSON-puro de un dimensionado dentro de `ExperimentoE5.resultados`.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from qrecauda.datos import ExperimentoE5
from qrecauda.dominio.entropia import h_min_con_defecto
from qrecauda.dominio.errores import EntradaInvalida
from qrecauda.dominio.metricas import Medida, Metrica, Veredicto

Resultado = Mapping[str, object]


def resultado_de(exp: ExperimentoE5, dimensionado: str) -> Resultado:
    hallados = [r for r in exp.resultados if r.get("dimensionado") == dimensionado]
    if len(hallados) != 1:
        raise EntradaInvalida(f"{exp.fuente}/{exp.semilla}: se esperaba un resultado de {dimensionado!r}, hay {len(hallados)}")
    return hallados[0]


def entregada(r: Resultado) -> bool:
    return r.get("estado") == "entregada"


def medidas_de(r: Resultado) -> tuple[Medida, ...]:
    return tuple(Medida(Metrica(m[0]), float(m[1]), float(m[2]), bool(m[3])) for m in r.get("medidas", []))  # type: ignore[attr-defined]


def bits_de_clave(r: Resultado) -> int:
    return int(r["bits_clave"]) if entregada(r) else 0  # type: ignore[call-overload]


def aprobada(r: Resultado) -> bool:
    """Entregó clave y esta pasa M1–M5, TODAS presentes (una ausente no aprueba)."""
    return entregada(r) and Veredicto(medidas_de(r)).calidad_de_clave_aprobada


def rechazada(r: Resultado) -> bool:
    """Sin clave, o con una que no pasa M1–M5: la cadena la rechaza."""
    return not aprobada(r)


def tasa_bps(r: Resultado) -> float:
    """Bits de clave por segundo de pared de la cadena entera (la definición de M6)."""
    seg = float(r["segundos"])  # type: ignore[arg-type]
    return bits_de_clave(r) / seg if seg > 0 else math.inf


def techo_k1(bits_crudos: int, peso: float, p_fresca_max: float) -> int:
    """K1: una clave no puede tener más bits que la min-entropía analítica de la fuente (necesario, no suficiente)."""
    return math.floor(h_min_con_defecto(peso, p_fresca_max) * bits_crudos)


def k1(r: Resultado, techo: int) -> bool:
    return bits_de_clave(r) <= techo


def k2(r: Resultado, bits_buena: int, fraccion: float) -> bool:
    return bits_de_clave(r) <= fraccion * bits_buena


def acortada(r: Resultado, techo: int, bits_buena: int, fraccion: float) -> bool:
    return aprobada(r) and k1(r, techo) and k2(r, bits_buena, fraccion)


def g2(r_conservador: Resultado, r_mcv: Resultado, fraccion: float) -> bool:
    return bits_de_clave(r_conservador) >= fraccion * bits_de_clave(r_mcv)


# ------------------------------------------------------------------ controles


def d5_cumple(exps: Sequence[ExperimentoE5], techo_defectuosa: float, piso_buena: float, defectuosas: Sequence[str]) -> bool:
    """D5: el 90B ve el defecto en la muestra que entra a Peres (defectuosas < techo) y no ve uno en la buena (≥ piso)."""
    return all(
        e.h_90b_fuente < techo_defectuosa if e.fuente in defectuosas else e.h_90b_fuente >= piso_buena for e in exps
    )  # fmt: skip


def p5_cumple(exps: Sequence[ExperimentoE5]) -> bool:
    """P5: dentro de cada (semilla, fuente), todos los dimensionados partieron de la misma muestra (sha256 idéntico)."""
    return all(len({str(r.get("sha256_muestra")) for r in e.resultados}) == 1 for e in exps)
