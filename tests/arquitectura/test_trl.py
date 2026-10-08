"""La matriz de TRL (docs/TRL.md) cita sólo evidencia que existe y el TRL del sistema es el de la fila más baja (T.TRL)."""

import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
TEXTO = (RAIZ / "docs" / "TRL.md").read_text()
NODOS = {n["id"] for n in json.loads((RAIZ / "plan" / "plan.json").read_text())["nodos"]}
CORRIDAS = RAIZ / "registro" / "corridas"
VEREDICTOS = {
    v["corrida"]: v for v in (json.loads(linea) for linea in (RAIZ / "registro" / "veredictos.jsonl").read_text().splitlines() if linea)
}


def _filas():
    filas = []
    for linea in TEXTO.split("## TRL del sistema")[0].splitlines():
        celdas = [c.strip() for c in linea.strip().strip("|").split("|")]
        if linea.startswith("|") and len(celdas) == 6 and re.fullmatch(r"\d", celdas[3]):
            filas.append(
                {
                    "componente": celdas[0],
                    "nodos": re.findall(r"`([^`]+)`", celdas[1]),
                    "corridas": re.findall(r"`([^`]+)`", celdas[2]),
                    "sin_hw": int(celdas[3]),
                    "con_hw": celdas[4],
                }
            )
    return filas


def _corrida(cid):
    return json.loads((CORRIDAS / f"{cid}.json").read_text())


def test_hay_una_fila_por_componente():
    assert len(_filas()) >= 7


def test_toda_fila_cita_nodos_existentes():
    for f in _filas():
        assert f["nodos"], f["componente"]
        assert not [n for n in f["nodos"] if n not in NODOS], f["componente"]


def test_toda_fila_cita_corridas_existentes():
    for f in _filas():
        assert f["corridas"], f["componente"]
        faltan = [c for c in f["corridas"] if not (CORRIDAS / f"{c}.json").exists()]
        assert not faltan, f"{f['componente']}: {faltan}"


def test_trl4_exige_repetibilidad_y_preinscripcion():
    for f in _filas():
        if f["sin_hw"] >= 4:
            assert any(n.startswith("P.") for n in f["nodos"]), f"{f['componente']}: TRL 4 sin preinscripción"
            assert any(len(_corrida(c)["artefactos"]) >= 3 for c in f["corridas"]), f"{f['componente']}: n < 3"


def test_veredicto_que_no_cumple_no_sostiene_trl4():
    for f in _filas():
        for c in f["corridas"]:
            v = VEREDICTOS.get(c)
            if v is not None and not v["aprobado"]:
                assert f["sin_hw"] < 4, f"{f['componente']} cita {c}, que NO CUMPLE"


def test_la_latencia_refleja_el_no_cumple_de_m7():
    assert VEREDICTOS["C.E3"]["aprobado"] is False
    fila = next(f for f in _filas() if "Latencia" in f["componente"])
    assert fila["sin_hw"] <= 3 and "E3" in fila["nodos"]


def test_trl_con_hardware_exige_corrida_real():
    hw = _corrida("HW")
    for f in _filas():
        if f["con_hw"] != "n/m":
            assert hw.get("hardware_real") is True and hw.get("job_id"), f["componente"]


def test_trl_del_sistema_es_el_de_la_fila_mas_baja():
    declarado = int(re.search(r"\*\*TRL del sistema: (\d)\*\*", TEXTO).group(1))
    assert declarado == min(f["sin_hw"] for f in _filas())
