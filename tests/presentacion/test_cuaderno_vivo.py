"""F7.08: el cuaderno «vivo» está guardado con sus salidas, tiene su celda de parámetros y no filtra rutas ni secretos."""

from __future__ import annotations

import json
from pathlib import Path

CUADERNO = Path(__file__).resolve().parents[2] / "notebooks" / "qrecauda_vivo.ipynb"


def _celdas() -> list[dict]:
    return json.loads(CUADERNO.read_text())["cells"]


def test_la_celda_de_parametros_ofrece_aer_e_ibm():
    codigo = ["".join(c["source"]) for c in _celdas() if c["cell_type"] == "code"]
    assert 'FUENTE = "aer"' in codigo[0] and '"ibm"' in codigo[0] and 'TOKEN_FILE = ""' in codigo[0]


def test_esta_ejecutado_sin_errores_y_con_el_rotulo_de_origen():
    salidas = [o for c in _celdas() if c["cell_type"] == "code" for o in c["outputs"]]
    assert salidas and not any(o["output_type"] == "error" for o in salidas)
    texto = "".join("".join(o.get("text", "")) for o in salidas)
    assert "simulado: Aer es pseudoaleatorio, sin origen cuántico" in texto
    assert "descifrado OK: True" in texto and "AES-256-GCM" in texto and "p mono" in texto


def test_no_lleva_rutas_absolutas_ni_el_nombre_de_un_token():
    t = CUADERNO.read_text()
    assert "/home/" not in t and "/mnt/" not in t
