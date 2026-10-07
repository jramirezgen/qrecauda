# -*- coding: utf-8 -*-
"""CLI del DAG de un proyecto (vendorizado desde la skill dag-de-proyecto; no se edita la copia).

    python3 plan/dag.py validar            # plan + historia + registro + append-only; sale con 1 si algo falla
    python3 plan/dag.py siguiente          # lo desbloqueado, los menos profundos primero
    python3 plan/dag.py estado             # escribe ESTADO.md
    python3 plan/dag.py estado --comprobar # sale con 1 si ESTADO.md no es su regeneración

El estado de cada nodo sale de registro/nodos.jsonl (manda la última línea), nunca se edita en el plan.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dag_lib as D  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]


def cargar():
    conf = D.Config.leer(RAIZ / "plan" / "dag.json")
    plan = json.loads((RAIZ / "plan" / "plan.json").read_text())
    plan["nodos"] = D.aplicar_registro(plan["nodos"], RAIZ)
    return conf, plan


def fallos_de(conf, plan):
    anterior = D._git(RAIZ, "show", "HEAD:plan/plan.json")
    anterior = json.loads(anterior)["nodos"] if anterior else None
    f = D.validar(plan["nodos"], RAIZ, conf, anterior, plan.get("degradaciones", {}))
    f += D.validar_historia(D.versiones_del_plan(RAIZ), conf.historia_desde)
    f += D.validar_registro(RAIZ, conf) + D.violaciones_append_only(RAIZ)
    if (RAIZ / "docs" / "bitacora").is_dir():
        f += D.violaciones_append_only(RAIZ, "docs/bitacora", ".md")
    return f


def main(argv):
    orden = argv[0] if argv else "validar"
    conf, plan = cargar()
    fallos = fallos_de(conf, plan)
    if fallos:
        raise SystemExit("✗ el DAG no cumple dag_lib:\n  " + "\n  ".join(fallos))
    if orden == "validar":
        print(f"{len(plan['nodos'])} nodos · reglas en verde")
    elif orden == "siguiente":
        for x in D.listos(plan["nodos"]):
            print(f"{x['id']:10} {x['tipo']:14} {x['titulo']}")
    elif orden == "estado":
        destino, texto = RAIZ / "ESTADO.md", D.estado_md(plan, conf)
        if "--comprobar" in argv:
            if not destino.exists() or destino.read_text() != texto:
                raise SystemExit("✗ ESTADO.md no es su regeneración: python3 plan/dag.py estado")
            print("ESTADO.md al día")
        else:
            destino.write_text(texto)
            print("ESTADO.md regenerado")
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
