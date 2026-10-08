"""Diagnóstico previo a P.E5 (NO es una corrida del plan, no vale como resultado): ¿qué hace HOY el pipeline con dependencia entre bits?

Bits frescos de un PRNG (sustituto del Aer con twirling, que da bits casi IID) con un defecto encima, semillas 1 y 2 (NO las
20261007/8/9 de la corrida), 8 qubits × 400 000 disparos, tres dimensionados: «mcv» (0.1.0), «min» (mínimo MCV–90B sobre el pool) y
«cons» (min + contabilidad con el 90B de la muestra cruda). Sirve para fijar el DISEÑO de E5 (qué fuentes, qué techo): los umbrales de E5
salen de la teoría (techo analítico) y de este diagnóstico sólo en su orden de magnitud (docs/preinscripciones/E5.md).

    OMP_NUM_THREADS=1 .venv/bin/python spikes/S05_control_negativo/diagnostico.py   # escribe diagnostico.json junto a este fichero
"""

from __future__ import annotations

import json
from pathlib import Path

from qrecauda.adaptadores.defectos import FuenteConDefecto, patron, persistencia
from qrecauda.adaptadores.min_entropia import MUESTRAS_MIN, EstimadorNist90B
from qrecauda.adaptadores.nist import ValidadorNist
from qrecauda.adaptadores.prng import FuentePrng
from qrecauda.aplicacion.pipeline import ParametrosPipeline, ejecutar
from qrecauda.dominio.entropia import EstimadorMCV, EstimadorMinimo, h_min_con_defecto
from qrecauda.dominio.errores import EntropiaInsuficiente
from qrecauda.dominio.extractores import peres
from qrecauda.transversal.observabilidad import RelojMonotonico

P_FRESCA_MAX = 0.51
PESOS = {"markov": 0.8, "markov_fuerte": 0.9, "periodica": 0.9}


def main() -> None:
    p = ParametrosPipeline(8, 400_000)
    val, e90 = ValidadorNist(), EstimadorNist90B()
    minimo = EstimadorMinimo([(EstimadorMCV(), None), (e90, MUESTRAS_MIN)])
    fuente90 = EstimadorMinimo([(e90, MUESTRAS_MIN)])
    dims = {
        "mcv": {},
        "min": {"estimador": minimo, "estimador_de_salida": EstimadorMCV()},
        "cons": {"estimador": minimo, "estimador_de_fuente": fuente90, "estimador_de_salida": EstimadorMCV()},
    }
    salida = []
    for semilla in (1, 2):
        fuentes = {
            "buena": lambda s=semilla: FuentePrng(s),
            "markov": lambda s=semilla: FuenteConDefecto(FuentePrng(s), persistencia(PESOS["markov"], s + 7)),
            "markov_fuerte": lambda s=semilla: FuenteConDefecto(FuentePrng(s), persistencia(PESOS["markov_fuerte"], s + 7)),
            "periodica": lambda s=semilla: FuenteConDefecto(FuentePrng(s), patron(PESOS["periodica"], "00001111", s + 7)),
        }
        for nombre, fabrica in fuentes.items():
            techo = int(h_min_con_defecto(PESOS[nombre], P_FRESCA_MAX) * p.qubits * p.shots) if nombre in PESOS else None
            fila: dict[str, object] = {"semilla": semilla, "fuente": nombre, "techo_analitico_bits": techo}
            cruda = fabrica().generar(p.qubits, p.shots).bits
            fila["h_90b_muestra_cruda"] = round(e90.estimar(cruda[:MUESTRAS_MIN]), 4)  # la fuente, antes de Peres
            pool = peres(cruda, p.profundidad_peres)
            if len(pool) >= MUESTRAS_MIN:
                fila["h_90b_pool"] = round(e90.estimar(pool[:MUESTRAS_MIN]), 4)  # tras Peres: la dependencia se reparte
            for dim, kw in dims.items():
                try:
                    r = ejecutar(fabrica(), val, RelojMonotonico(), p, **kw)  # type: ignore[arg-type]
                    fila[dim] = {"bits_clave": len(r.clave), "h": round(r.h_min, 4), "aprobada": r.veredicto.calidad_de_clave_aprobada}
                except EntropiaInsuficiente as e:
                    fila[dim] = {"rechazada": str(e)}
            salida.append(fila)
            print(fila, flush=True)
    (Path(__file__).parent / "diagnostico.json").write_text(json.dumps(salida, indent=1, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
