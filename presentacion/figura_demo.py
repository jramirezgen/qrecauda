#!/usr/bin/env python3
"""Figura de la demo de las tres ramas (PRNG, fuente Aer sin mitigar, fuente Aer mitigada).

Lee   registro/corridas/*.json (artefactos de C.E1a, C.E1b y C.E1c). Una rama sin corrida no se dibuja.
Escribe docs/pitch/fig/demo_tres_ramas.{pdf,png}.

Uso (desde la raíz del repo, con el entorno del proyecto):
    .venv/bin/python presentacion/figura_demo.py

Qué muestra: a la izquierda, el sesgo (M1) de la muestra que entra al pipeline en cada rama; a la derecha, el de la
clave que sale. La mitigación cambia la entrada; la clave final pasa en las tres ramas. Por eso pasar la batería
no prueba el origen de los bits.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "docs" / "pitch" / "fig"
UMBRAL_M1 = 0.01

# (corrida, etiqueta, etapa de entrada, color Okabe-Ito)
RAMAS = (
    ("C.E1a", "PRNG clásico", "cruda", "#0072B2"),
    ("C.E1b", "Aer sin mitigar", "cruda", "#D55E00"),
    ("C.E1c", "Aer mitigado", "mitigada", "#009E73"),
)


def _artefactos() -> dict[str, list[dict]]:
    por_id: dict[str, list[dict]] = {}
    for p in sorted((RAIZ / "registro" / "corridas").glob("*.json")):
        d = json.loads(p.read_text())
        if "artefactos" in d or "etapas" not in d:
            continue
        por_id.setdefault(d.get("corrida", p.stem), []).append(d)
    return por_id


def _m1(etapa: list) -> float:
    return next(m[1] for m in etapa if m[0] == "M1_sesgo")


def main() -> int:
    arte = _artefactos()
    ramas = [(c, e, et, col) for c, e, et, col in RAMAS if arte.get(c)]
    if not ramas:
        print("sin corridas C.E1a/b/c en registro/corridas/", file=sys.stderr)
        return 1
    plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False})
    fig, ejes = plt.subplots(1, 2, figsize=(10, 4.2), sharey=True)
    titulos = ("Entrada: sesgo de la muestra de bits", "Salida: sesgo de la clave")
    for k, (ax, tit) in enumerate(zip(ejes, titulos)):
        for i, (cid, etiqueta, etapa, col) in enumerate(ramas):
            vals = [_m1(d["etapas"][etapa if k == 0 else "clave"]) for d in arte[cid]]
            vals = [max(v, 1e-5) for v in vals]
            ax.scatter(np.full(len(vals), i) + np.linspace(-0.08, 0.08, len(vals)), vals, s=70, color=col, zorder=3)
            ax.hlines(np.median(vals), i - 0.22, i + 0.22, color=col, lw=2, zorder=2)
        ax.axhline(UMBRAL_M1, color="#444444", ls="--", lw=1)
        ax.text(len(ramas) - 0.55, UMBRAL_M1 * 1.15, "umbral M1", ha="right", va="bottom", fontsize=9, color="#444444")
        ax.set_yscale("log")
        ax.set_ylim(5e-6, 0.2)
        ax.set_xlim(-0.6, len(ramas) - 0.4)
        ax.set_xticks(range(len(ramas)), [r[1] for r in ramas])
        ax.set_title(tit, fontsize=12, loc="left")
        ax.grid(axis="y", color="#DDDDDD", lw=0.6, zorder=0)
    ejes[0].set_ylabel("sesgo (escala logarítmica)")
    ejes[1].text(0.5, 0.06, "las tres claves pasan: pasar no prueba origen", transform=ejes[1].transAxes,
                 ha="center", fontsize=10, color="#222222")
    n = {c: len(arte[c]) for c, *_ in ramas}
    fig.text(0.01, 0.005, f"Semillas por rama: {', '.join(f'{c} {v}' for c, v in n.items())}. Cada punto es una semilla; la raya es la mediana.",
             fontsize=8.5, color="#555555")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    SALIDA.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(SALIDA / f"demo_tres_ramas.{ext}", dpi=200)
    print("escrito docs/pitch/fig/demo_tres_ramas.{pdf,png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
