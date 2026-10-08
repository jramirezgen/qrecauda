"""Calibración del control P1 de E1 (enmienda 2026-10-07): el 90B (`ea_non_iid -i -a`) sobre las cuatro fuentes de C.E1d.

Mide, con las MISMAS clases de fuente que usa el ejecutor (adaptadores.prng) y el mismo estimador (adaptadores.min_entropia),
1 000 000 de bits por fuente y semilla, en 11 semillas: las tres declaradas de E1 (20261007/8/9) y ocho de calibración
(20261010–20261017). No es una corrida de E1 ni escribe en registro/: es el sustento del piso de la enmienda.

Uso:  OMP_NUM_THREADS=1 .venv/bin/python spikes/S04_90b/calibracion_p1.py   (necesita /tmp/qrecauda_nist90b/ea_non_iid)
Escribe calibracion_p1.json junto a este archivo.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parents[1] / "src"))

from qrecauda.adaptadores.min_entropia import EstimadorNist90B  # noqa: E402
from qrecauda.adaptadores.prng import FuenteMarkov, FuentePeriodica, FuentePrng  # noqa: E402
from qrecauda.dominio.entropia import min_entropia_mcv  # noqa: E402

N = 1_000_000
DECLARADAS = (20261007, 20261008, 20261009)
CALIBRACION = tuple(range(20261010, 20261018))
SEMILLAS = DECLARADAS + CALIBRACION


def fuentes(semilla: int) -> dict:
    # parámetros de declaraciones/E1.toml [criterios.c_e1d]
    return {
        "ideal": FuentePrng(semilla),
        "markov": FuenteMarkov(semilla, 0.8),
        "sesgada": FuentePrng(semilla, sesgo=0.7 - 0.5),
        "periodica": FuentePeriodica("00001111"),
    }


def main() -> None:
    est = EstimadorNist90B()
    filas = []
    for s in SEMILLAS:
        fila = {"semilla": s, "declarada": s in DECLARADAS}
        for nombre, f in fuentes(s).items():
            bits = f.generar(1, N).bits
            fila[nombre] = {"h_90b": round(est.estimar(bits), 6), "mcv": round(min_entropia_mcv(bits), 6)}
        filas.append(fila)
        print(s, {k: v["h_90b"] for k, v in fila.items() if isinstance(v, dict)}, flush=True)
    ideal = [f["ideal"]["h_90b"] for f in filas]
    markov90 = [f["markov"]["h_90b"] for f in filas]
    markov_mcv = [f["markov"]["mcv"] for f in filas]
    piso = math.floor(min(ideal) * 10) / 10  # hacia abajo a 0,1
    resumen = {
        "ideal_90b": {"min": min(ideal), "max": max(ideal), "n_sobre_0_9": sum(v > 0.9 for v in ideal), "n": len(ideal)},
        "markov_90b": {"min": min(markov90), "max": max(markov90)},
        "markov_mcv": {"min": min(markov_mcv), "max": max(markov_mcv)},
        "piso_ideal_redondeado_abajo_0_1": piso,
        "separacion_ideal_menos_markov": round(min(ideal) - max(markov90), 6),
    }
    out = {"herramienta": "ea_non_iid v1.1.8 -i -a, 1 bit/símbolo", "bits": N, "semillas": list(SEMILLAS), "filas": filas, "resumen": resumen}
    (AQUI / "calibracion_p1.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(json.dumps(resumen, indent=1))


if __name__ == "__main__":
    main()
