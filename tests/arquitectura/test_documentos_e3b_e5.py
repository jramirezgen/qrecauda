"""Los documentos que resumen resultados reflejan los veredictos de E3, E3b y E5 y no inventan hardware.

El registro manda: si un veredicto cambia, estos tests obligan a releer los documentos. No comprueban cifras (eso lo
hace ``test_cifras_del_pitch.py`` para el pitch y el deck); comprueban que el relato no contradice el registro.
"""

import json
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
VEREDICTOS = {v["corrida"]: v for v in (json.loads(x) for x in (RAIZ / "registro" / "veredictos.jsonl").read_text().splitlines() if x)}
DOCUMENTOS = {
    "README": RAIZ / "README.md",
    "PITCH": RAIZ / "docs" / "pitch" / "PITCH.md",
    "DECK": RAIZ / "docs" / "pitch" / "DECK.md",
    "GUION": RAIZ / "docs" / "pitch" / "GUION.md",
    "TRL": RAIZ / "docs" / "TRL.md",
    "ROADMAP": RAIZ / "docs" / "ROADMAP.md",
    "PAPER": RAIZ / "docs" / "paper" / "paper.md",
    "CHANGELOG": RAIZ / "CHANGELOG.md",
}


def _texto(nombre: str) -> str:
    return DOCUMENTOS[nombre].read_text(encoding="utf-8")


def test_los_veredictos_de_partida_son_los_que_el_relato_da_por_sentados():
    assert VEREDICTOS["C.E3"]["aprobado"] is False, "E3 (0.1.0) sigue en NO CUMPLE y no se reabre"
    assert VEREDICTOS["C.E3b"]["aprobado"] is True
    assert VEREDICTOS["C.E5"]["aprobado"] is True
    assert len(json.loads((RAIZ / "registro" / "corridas" / "C.E3b.json").read_text())["artefactos"]) == 3
    assert len(json.loads((RAIZ / "registro" / "corridas" / "C.E5.json").read_text())["artefactos"]) == 12


@pytest.mark.parametrize("nombre", ["README", "PITCH", "DECK", "GUION", "TRL", "ROADMAP", "PAPER", "CHANGELOG"])
def test_cada_documento_nombra_e3b_y_e5(nombre):
    t = _texto(nombre)
    assert "E3b" in t, f"{nombre} no menciona E3b"
    assert "E5" in t, f"{nombre} no menciona E5"


@pytest.mark.parametrize("nombre", ["README", "PITCH", "GUION", "PAPER", "TRL", "ROADMAP"])
def test_e3_sigue_declarado_no_cumple_junto_a_e3b(nombre):
    t = _texto(nombre)
    assert re.search(r"(?i)no cumpl", t), f"{nombre} perdió el NO CUMPLE de E3"


@pytest.mark.parametrize("nombre", ["README", "PITCH", "DECK", "GUION", "TRL", "ROADMAP", "PAPER", "CHANGELOG"])
def test_ningun_documento_afirma_un_resultado_en_hardware(nombre):
    t = _texto(nombre)
    assert not re.search(r"(?i)corrida real (cumple|cumplió|terminó)|resultado en hardware real (existe|obtenido)", t)
    assert not re.search(r"(?i)\bjob_id\s*[:=]\s*[\"']?[a-z0-9]{10,}", t), "un job_id real no debe aparecer en la documentación"


def test_el_trl_del_sistema_sigue_en_3_y_la_latencia_con_reserva_no_lo_sube():
    t = _texto("TRL")
    assert "**TRL del sistema: 3**" in t
    fila = next(linea for linea in t.splitlines() if linea.startswith("| Latencia de transacción con la clave de una reserva"))
    assert "`C.E3b`" in fila and "| 4 |" in fila
    assert "No sube al sistema" in fila


def test_el_dimensionado_conservador_se_declara_opt_in_y_no_re_medido():
    for nombre in ("README", "PAPER", "CHANGELOG"):
        t = _texto(nombre)
        assert "opt-in" in t, nombre
        assert re.search(r"(?i)no se re-midi", t), f"{nombre} debe decir que E3 y E3b no se re-midieron con el conservador"


def test_la_version_0_2_0_no_se_declara_publicada():
    cambios = _texto("CHANGELOG")
    assert "0.2.0 en preparación" in cambios
    assert not re.search(r"(?m)^## \[0\.2\.0\]", cambios), "la 0.2.0 aún no está publicada: no lleva entrada fechada"
    assert 'version = "0.1.0"' in (RAIZ / "pyproject.toml").read_text()
