"""Lo vendorizado de dag-de-proyecto no ha divergido de su skill, y el DAG del repo es válido."""
import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
SKILL = Path("/mnt/f/skills/_personales/dag-de-proyecto/scripts")


@pytest.mark.parametrize("nombre", ['dag_lib.py', 'dag.py'])
def test_lo_vendorizado_no_ha_divergido(nombre):
    if not SKILL.is_dir():
        pytest.skip("la skill no está montada; el repo sigue siendo autónomo")
    h = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    assert h(RAIZ / "plan" / nombre) == h(SKILL / nombre), f"plan/{nombre} divergió: corre instalar.py --aplicar"


def test_el_dag_es_valido_y_estado_al_dia():
    r = subprocess.run([sys.executable, str(RAIZ / "plan" / "dag.py"), "estado", "--comprobar"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr + r.stdout


def test_plan_json_es_la_regeneracion_de_construir_dag():
    r = subprocess.run([sys.executable, str(RAIZ / "plan" / "construir_dag.py"), "--comprobar"], capture_output=True, text=True)
    assert r.returncode == 0, "plan.json no coincide con plan/construir_dag.py: regenéralo"
