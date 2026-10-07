import dataclasses

import pytest

from qrecauda.dominio.errores import EntradaInvalida
from qrecauda.transversal.configuracion import Configuracion


def test_es_inmutable():
    cfg = Configuracion()
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.shots = 5  # type: ignore[misc]


def test_cargar_desde_toml_y_clave_desconocida_aborta(tmp_path):
    ok = tmp_path / "ok.toml"
    ok.write_text("qubits = 4\nshots = 10\n")
    assert Configuracion.cargar(ok).qubits == 4
    mala = tmp_path / "mala.toml"
    mala.write_text("qubits = 4\nshotz = 10\n")
    with pytest.raises(EntradaInvalida, match="shotz"):
        Configuracion.cargar(mala)


def test_el_token_entra_por_ruta_desde_el_entorno(monkeypatch, tmp_path):
    monkeypatch.setenv("QRECAUDA_IBM_TOKEN_FILE", str(tmp_path / "t.txt"))
    cfg = Configuracion.cargar(None)
    assert cfg.ibm_token_ruta == str(tmp_path / "t.txt")


@pytest.mark.parametrize("mapa", [{"qubits": "8"}, {"shots": 1.5}, {"qubits": True}, {"backend": 3}, {"semilla": None}])
def test_tipo_equivocado_aborta(mapa):
    with pytest.raises(EntradaInvalida, match="tipo"):
        Configuracion.desde_mapa(mapa)


def test_como_dict_es_estable_y_no_lleva_valores_de_secreto():
    d = Configuracion(backend="ibm", ibm_token_ruta="/ruta/t.txt").como_dict()
    assert d["ibm_token_ruta"] == "/ruta/t.txt"
    assert list(d) == sorted(d)


def test_omp_num_threads_se_lee_aqui_y_solo_aqui(monkeypatch):
    from qrecauda.transversal.configuracion import omp_num_threads

    monkeypatch.delenv("OMP_NUM_THREADS", raising=False)
    assert omp_num_threads() is None
    monkeypatch.setenv("OMP_NUM_THREADS", "1")
    assert omp_num_threads() == "1"
