"""Los criterios y controles de E1 (docs/preinscripciones/E1.md), como funciones puras sobre lo ya medido.

UNA sola definición: el ejecutor las usa para calcular los controles N1, D1 y P1, y el juez las vuelve a calcular sobre los
artefactos releídos (un control que dice «ok» en el manifiesto pero que los datos desmienten invalida la corrida).
Los umbrales son los de `dominio.metricas`; aquí no se teclea ninguno salvo el 0,9 del 90B, que ES el de M2.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from qrecauda.datos import InformeCorrida, MedidaDeFuente
from qrecauda.dominio.errores import EntradaInvalida
from qrecauda.dominio.metricas import UMBRALES, Medida, Metrica

M1, M2, M3, M4, M5 = Metrica.SESGO, Metrica.MIN_ENTROPIA, Metrica.MONOBIT, Metrica.RUNS, Metrica.CHI2
ESTRUCTURA = (M1, M3, M4, M5)  # lo que se mide en los tres puntos
CLAVE = (M1, M2, M3, M4, M5)
UMBRAL_90B = UMBRALES[Metrica.MIN_ENTROPIA].valor  # 0,9: el de M2 (clave); en P1 sólo fija la ceguera del MCV, no el piso del 90B
FUENTES_E1D = ("sesgada", "periodica", "markov", "ideal")


def medida(ms: Sequence[Medida], metrica: Metrica) -> Medida:
    for m in ms:
        if m.metrica is metrica:
            return m
    raise EntradaInvalida(f"falta {metrica.value} entre las medidas: no se juzga lo que no se midió")


def pasan(ms: Sequence[Medida], metricas: Iterable[Metrica]) -> bool:
    """Todas las métricas pedidas están medidas y cumplen (una ausente es un error, no un «cumple»)."""
    return all(medida(ms, k).cumple for k in metricas)


def fallan(ms: Sequence[Medida], metricas: Iterable[Metrica]) -> list[str]:
    return [f"{k.value}={medida(ms, k).valor:.6g}" for k in metricas if not medida(ms, k).cumple]


def etapa(i: InformeCorrida, nombre: str) -> tuple[Medida, ...]:
    if nombre not in i.etapas:
        raise EntradaInvalida(f"el informe {i.corrida}/{i.semilla} no tiene la etapa {nombre!r}")
    return tuple(i.etapas[nombre])


# ------------------------------------------------------------------ controles


def n1_cumple(a: InformeCorrida) -> bool:
    """N1 (C.E1a): la batería acepta una fuente ideal: la cruda pasa M1, M3, M4, M5 y la clave M1–M5."""
    return pasan(etapa(a, "cruda"), ESTRUCTURA) and pasan(a.veredicto.medidas, CLAVE)


def d1_cumple(b: InformeCorrida, analitico: float, tolerancia: float) -> bool:
    """D1 (C.E1b): el sesgo medido de la cruda coincide con el inyectado, |medido − analítico| ≤ tolerancia."""
    return abs(medida(etapa(b, "cruda"), M1).valor - analitico) <= tolerancia


def p1_detalle(fuentes: Mapping[str, MedidaDeFuente], piso_ideal: float, techo_rechazo: float) -> dict[str, bool]:
    """P1 (C.E1d, enmienda 2026-10-07 (2)): por fuente, si el instrumento SEPARA lo bueno de lo malo. Las cuatro deben estar.

    `piso_ideal` y `techo_rechazo` salen de `declaraciones/E1.toml [criterios.c_e1d]` (calibrados con 11 medidas del 90B de la
    ideal, spikes/S04_90b/calibracion_p1.json); aquí no se teclean. El piso es inclusivo y el techo estricto.
    """
    if not piso_ideal > techo_rechazo:
        raise EntradaInvalida(
            f"P1: el piso de la ideal ({piso_ideal}) debe superar el techo ({techo_rechazo}): sin hueco no hay separación"
        )
    falta = [f for f in FUENTES_E1D if f not in fuentes]
    if falta:
        raise EntradaInvalida(f"C.E1d: faltan las fuentes {falta}")
    s, p, k, i = (fuentes[f] for f in FUENTES_E1D)
    return {
        "sesgada": not medida(s.medidas, M1).cumple and not medida(s.medidas, M3).cumple,
        "periodica": not pasan(p.medidas, ESTRUCTURA) or p.h_90b < techo_rechazo,
        "markov": k.h_90b < techo_rechazo and k.mcv >= UMBRAL_90B,  # el MCV la deja pasar, el 90B la rechaza (discrepancia 8)
        "ideal": pasan(i.medidas, ESTRUCTURA) and i.h_90b >= piso_ideal,
    }


def p1_cumple(fuentes: Mapping[str, MedidaDeFuente], piso_ideal: float, techo_rechazo: float) -> bool:
    return all(p1_detalle(fuentes, piso_ideal, techo_rechazo).values())


def umbrales_p1(decl_c_e1d: Mapping[str, object]) -> tuple[float, float]:
    """(piso_ideal_90b, techo_rechazo_90b) de `[criterios.c_e1d]`: una sola lectura para el ejecutor y el juez."""
    try:
        return float(decl_c_e1d["piso_ideal_90b"]), float(decl_c_e1d["techo_rechazo_90b"])  # type: ignore[arg-type]
    except KeyError as e:
        raise EntradaInvalida(f"[criterios.c_e1d] no declara {e}: P1 no se juzga sin su piso y su techo") from e


# ------------------------------------------------------------------ criterios que deciden


def b1_cumple(b: InformeCorrida) -> bool:
    """B1 (C.E1b): la cruda FALLA M1 o M3."""
    c = etapa(b, "cruda")
    return not medida(c, M1).cumple or not medida(c, M3).cumple


def m1_cumple(c: InformeCorrida) -> bool:
    """M-1 (C.E1c, tras la enmienda 2026-10-07): la mitigada pasa M1 y M3. M4 y M5 de la mitigada sólo se reportan."""
    return pasan(etapa(c, "mitigada"), (M1, M3))


def m2_cumple(c: InformeCorrida) -> bool:
    """M-2 (C.E1c): la clave pasa M1, M2, M3, M4 y M5."""
    return pasan(c.veredicto.medidas, CLAVE)
