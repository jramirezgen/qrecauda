"""Tablas y figuras del pitch, calculadas SÓLO desde `registro/` (ninguna cifra se teclea).

Funciones puras: leen `registro/corridas/*.json` y `registro/veredictos.jsonl` y devuelven listas de dicts (tablas) o
`matplotlib.figure.Figure` (sin `pyplot`, sin backend global). `notebooks/qrecauda.ipynb` sólo llama a este módulo.

Nota de diseño: `docs/paper/figuras.py` es un script (no un paquete importable) y `presentacion` no puede depender de
`docs/`; aquí sólo se comparte la paleta Okabe-Ito, y la lógica de datos se reescribe mínima y probada.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from statistics import mean
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from matplotlib.figure import Figure

__all__ = [
    "fig_e1_fuentes",
    "fig_e2_sesgo",
    "fig_e3_cuello",
    "localizar_raiz",
    "tabla_e1",
    "tabla_e1_fuentes",
    "tabla_e2",
    "tabla_e3",
    "tabla_perfil_b",
    "tabla_veredictos",
    "a_markdown",
    "a_png",
]

Fila = dict[str, Any]
Tabla = list[Fila]

# Paleta Okabe-Ito (apta para daltonismo); cada figura repite en texto lo que codifica el color.
VERDE, BERMELLON, AZUL, NARANJA, GRIS = "#009E73", "#D55E00", "#0072B2", "#E69F00", "#8A8A8A"


# ── lectura ───────────────────────────────────────────────────────────────────────────────────
def localizar_raiz(desde: Path | None = None) -> Path:
    """Sube desde `desde` (por defecto el cwd) hasta la carpeta que contiene `registro/veredictos.jsonl`."""
    inicio = (desde or Path.cwd()).resolve()
    for p in (inicio, *inicio.parents):
        if (p / "registro" / "veredictos.jsonl").is_file():
            return p
    raise FileNotFoundError(f"no hay registro/veredictos.jsonl en {inicio} ni en sus padres")


def _jsonl(ruta: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in ruta.read_text(encoding="utf-8").splitlines() if x.strip()]


def _veredictos(raiz: Path) -> dict[str, dict[str, Any]]:
    """eureka -> ÚLTIMO veredicto de ese eureka (manda el último, como en el registro)."""
    return {v["eureka"]: v for v in _jsonl(raiz / "registro" / "veredictos.jsonl")}


def _corridas(raiz: Path, patron: str) -> list[dict[str, Any]]:
    return [json.loads(f.read_text(encoding="utf-8")) for f in sorted((raiz / "registro" / "corridas").glob(patron))]


def _medida(medidas: Iterable[Sequence[Any]], nombre: str) -> Sequence[Any]:
    return next(m for m in medidas if m[0] == nombre)


# ── tablas ────────────────────────────────────────────────────────────────────────────────────
def tabla_veredictos(raiz: Path) -> Tabla:
    """Un renglón por eureka: desenlace, resumen y commit juzgado."""
    return [
        {
            "eureka": e,
            "corrida": v["corrida"],
            "desenlace": v["desenlace"],
            "criterios_decisivos": sum(1 for c in v["criterios"] if c["decide"]),
            "criterios_que_fallan": sum(1 for c in v["criterios"] if c["decide"] and not c["cumple"]),
            "resumen": v["resumen"],
            "commit": v["commit"][:8],
        }
        for e, v in sorted(_veredictos(raiz).items())
    ]


def tabla_e1(raiz: Path) -> Tabla:
    """E1 por sub-corrida y semilla: métricas de la clave final (M1–M5), M2 de salida y bits de clave."""
    filas: Tabla = []
    for d in _corridas(raiz, "C.E1_*_informe_*.json"):
        clave = d["etapas"].get("clave") or d["etapas"].get("cruda")
        filas.append(
            {
                "corrida": d["corrida"],
                "semilla": d["semilla"],
                "origen": d["origen"],
                "M1_sesgo": _medida(clave, "M1_sesgo")[1],
                "M3_p": _medida(clave, "M3_nist_monobit")[1],
                "M4_p": _medida(clave, "M4_nist_runs")[1],
                "M5_p": _medida(clave, "M5_chi_cuadrado")[1],
                "h_min_salida": d["h_min_salida"],
                "bits_clave": d["bits_clave"],
                "pasa_M1_M5": all(m[3] for m in clave),
            }
        )
    return sorted(filas, key=lambda f: (f["corrida"], f["semilla"]))


def tabla_e1_fuentes(raiz: Path) -> Tabla:
    """Controles de E1d: min-entropía por 90B y por MCV de cada fuente, media de las semillas."""
    por: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for d in _corridas(raiz, "C.E1_*_fuente_*.json"):
        por[d["fuente"]].append(d)
    return [
        {
            "fuente": f,
            "semillas": len(ds),
            "bits": ds[0]["bits"],
            "h_90b_media": mean(x["h_90b"] for x in ds),
            "mcv_media": mean(x["mcv"] for x in ds),
        }
        for f, ds in sorted(por.items())
    ]


def tabla_e2(raiz: Path) -> Tabla:
    """E2 por (nivel de ruido, técnica): sesgo crudo y residual medios entre semillas y su IC95 medio."""
    por: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for d in _corridas(raiz, "C.E2_*_e2_*.json"):
        por[(d["nivel"], d["tecnica"])].append(d)
    filas: Tabla = []
    for (nivel, tec), ds in sorted(por.items()):
        crudo, resid = mean(x["sesgo_crudo"] for x in ds), mean(x["sesgo_residual"] for x in ds)
        filas.append(
            {
                "nivel": nivel,
                "tecnica": tec,
                "semillas": len(ds),
                "sesgo_crudo": crudo,
                "sesgo_residual": resid,
                "ic95_inf": mean(x["intervalo_residual"][0] for x in ds),
                "ic95_sup": mean(x["intervalo_residual"][1] for x in ds),
                "factor": crudo / resid if resid else float("inf"),
            }
        )
    return filas


def _umbral(detalle: str, valor: float) -> float:
    """El umbral de un criterio de E3 = valor medido / «cociente a umbral» que escribió el juez en su detalle."""
    m = re.search(r"cociente a umbral ([0-9.]+)", detalle)
    if not m:
        raise ValueError(f"el detalle no trae cociente a umbral: {detalle!r}")
    return valor / float(m.group(1))


def tabla_e3(raiz: Path) -> Tabla:
    """E3 (perfil A, el que decide): M6 y M7 p95 por semilla frente a su umbral, con el veredicto del juez."""
    crit = {c["id"]: c for c in _veredictos(raiz)["E3"]["criterios"]}
    filas: Tabla = []
    for d in _corridas(raiz, "C.E3_*_e3_*.json"):
        s = d["semilla"]
        t1, t2 = crit[f"T1/{s}"], crit[f"T2/{s}"]
        filas.append(
            {
                "semilla": s,
                "M6_bps": d["m6_bits_por_s"],
                "M6_umbral_bps": _umbral(t1["detalle"], d["m6_bits_por_s"]),
                "M6_cumple": t1["cumple"],
                "M7_p95_ms": d["m7_p95_ms"],
                "M7_umbral_ms": _umbral(t2["detalle"], d["m7_p95_ms"]),
                "M7_cumple": t2["cumple"],
                "repeticiones": d["repeticiones"],
            }
        )
    return filas


def tabla_perfil_b(raiz: Path) -> Tabla:
    """Perfil B de E3 (complementario, NO decide): transacciones por segundo con la reserva de claves."""
    return [
        {
            "semilla": d["semilla"],
            "tx_por_s": d["reporte"]["perfil_b"]["tx_por_s"],
            "transacciones": d["reporte"]["perfil_b"]["transacciones"],
            "ciclo_mediana_us": d["reporte"]["perfil_b"]["ciclo_us"]["mediana"],
            "ciclo_p95_us": d["reporte"]["perfil_b"]["ciclo_us"]["p95"],
            "entropia_insuficiente": d["reporte"]["perfil_b"]["entropia_insuficiente"],
            "decide": d["reporte"]["perfil_b"]["decide"],
        }
        for d in _corridas(raiz, "C.E3_*_e3_*.json")
    ]


def a_markdown(tabla: Tabla, *, cifras: int = 4) -> str:
    """Tabla de dicts a Markdown (para que el notebook la muestre sin pandas)."""
    if not tabla:
        return "_(vacía)_"
    cols = list(tabla[0])

    def fmt(v: Any) -> str:
        if isinstance(v, bool):
            return "sí" if v else "NO"
        if isinstance(v, float):
            return f"{v:.{cifras}g}"
        return str(v)

    filas = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    filas += ["| " + " | ".join(fmt(f[c]) for c in cols) + " |" for f in tabla]
    return "\n".join(filas)


def a_png(fig: Figure, dpi: int = 110) -> bytes:
    """La figura como PNG (para mostrarla en un cuaderno sin pyplot)."""
    from io import BytesIO

    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=dpi)
    return buf.getvalue()


# ── figuras ───────────────────────────────────────────────────────────────────────────────────
def fig_e3_cuello(raiz: Path) -> Figure:
    """M6 y M7 por semilla frente a su umbral (escala log). Verde = cumple, bermellón = no; el texto repite el color."""
    from matplotlib.figure import Figure

    filas = tabla_e3(raiz)
    x = [str(f["semilla"]) for f in filas]
    fig = Figure(figsize=(7, 3), layout="constrained")
    a, b = fig.subplots(1, 2)
    for ax, medida, unidad, umbral in ((a, "M6_bps", "bit/s", "M6_umbral_bps"), (b, "M7_p95_ms", "ms", "M7_umbral_ms")):
        cumple = "M6_cumple" if medida == "M6_bps" else "M7_cumple"
        ax.bar(x, [f[medida] for f in filas], color=[VERDE if f[cumple] else BERMELLON for f in filas])
        ax.axhline(filas[0][umbral], color="black", ls="--", lw=0.8)
        ax.set_yscale("log")
        ax.set_ylabel(unidad)
        for i, f in enumerate(filas):
            ax.annotate(f"{f[medida]:.4g}\n{'cumple' if f[cumple] else 'NO cumple'}", (i, f[medida]), ha="center", va="bottom", fontsize=7)
        ax.set_title(f"{medida[:2]}: umbral {filas[0][umbral]:.4g} {unidad}", loc="left", fontsize=8)
        ax.margins(y=0.6)
    return fig


def fig_e2_sesgo(raiz: Path) -> Figure:
    """E2: sesgo crudo (sin mitigar) frente a residual por nivel de ruido, técnica «ninguna» y «twirling_propio»."""
    from matplotlib.figure import Figure

    filas = tabla_e2(raiz)
    niveles = [
        n for n in dict.fromkeys(f["nivel"] for f in filas) if any(f["nivel"] == n and f["tecnica"] == "twirling_propio" for f in filas)
    ]
    crudo = {f["nivel"]: f["sesgo_crudo"] for f in filas if f["tecnica"] == "twirling_propio"}
    resid = {f["nivel"]: f for f in filas if f["tecnica"] == "twirling_propio"}
    fig = Figure(figsize=(6.5, 3), layout="constrained")
    ax = fig.subplots()
    xs = range(len(niveles))
    ax.bar([i - 0.2 for i in xs], [crudo[n] for n in niveles], 0.4, color=NARANJA, label="crudo (sin mitigar)")
    ax.bar([i + 0.2 for i in xs], [resid[n]["sesgo_residual"] for n in niveles], 0.4, color=AZUL, label="residual con twirling")
    ax.errorbar(
        [i + 0.2 for i in xs],
        [resid[n]["sesgo_residual"] for n in niveles],
        yerr=[
            [resid[n]["sesgo_residual"] - resid[n]["ic95_inf"] for n in niveles],
            [resid[n]["ic95_sup"] - resid[n]["sesgo_residual"] for n in niveles],
        ],
        fmt="none",
        ecolor="black",
        lw=0.8,
    )
    ax.set_yscale("symlog", linthresh=1e-4)
    ax.set_xticks(list(xs), niveles)
    ax.set_ylabel("sesgo |p̂ − ½|")
    ax.legend(frameon=False, fontsize=7)
    return fig


def fig_e1_fuentes(raiz: Path) -> Figure:
    """E1d: min-entropía 90B y MCV de cada fuente de control (las defectuosas deben caer bajo el umbral 0,5)."""
    from matplotlib.figure import Figure

    filas = tabla_e1_fuentes(raiz)
    fig = Figure(figsize=(6.5, 3), layout="constrained")
    ax = fig.subplots()
    xs = range(len(filas))
    ax.bar([i - 0.2 for i in xs], [f["h_90b_media"] for f in filas], 0.4, color=AZUL, label="90B")
    ax.bar([i + 0.2 for i in xs], [f["mcv_media"] for f in filas], 0.4, color=GRIS, label="MCV")
    ax.axhline(0.5, color="black", ls="--", lw=0.8)
    ax.set_xticks(list(xs), [f["fuente"] for f in filas])
    ax.set_ylabel("min-entropía por bit")
    ax.legend(frameon=False, fontsize=7)
    return fig
