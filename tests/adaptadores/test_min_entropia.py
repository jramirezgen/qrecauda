"""F5.02: min-entropía SP 800-90B (ea_non_iid oficial, S.04). Los tests con binario se saltan si no está compilado."""

import math
from pathlib import Path

import numpy as np
import pytest

from qrecauda.adaptadores.min_entropia import BINARIO_POR_DEFECTO, MUESTRAS_MIN, EstimadorNist90B
from qrecauda.dominio.bits import Bits
from qrecauda.dominio.entropia import min_entropia_mcv
from qrecauda.dominio.errores import EntropiaInsuficiente, FuenteNoDisponible

N = MUESTRAS_MIN
SEMILLA = 20261007
necesita_binario = pytest.mark.skipif(not BINARIO_POR_DEFECTO.is_file(), reason="falta ea_non_iid: bash spikes/S04_90b/build_nist.sh")


def test_menos_de_un_millon_de_muestras_es_entropia_insuficiente():
    with pytest.raises(EntropiaInsuficiente):
        EstimadorNist90B().estimar(Bits.desde([0, 1] * 1000))


def test_sin_binario_falla_con_la_instruccion_de_build():
    est = EstimadorNist90B(binario=Path("/no/existe/ea_non_iid"))
    with pytest.raises(FuenteNoDisponible, match="build_nist.sh"):
        est.estimar(Bits(np.zeros(N, dtype=np.uint8)))


@necesita_binario
def test_iid_sesgada_da_la_cota_conservadora_de_s04():
    rng = np.random.default_rng(SEMILLA)
    b = Bits((rng.random(N) < 0.7).astype(np.uint8))
    h = EstimadorNist90B().estimar(b)
    assert h == pytest.approx(0.322, abs=0.01)
    assert h <= -math.log2(0.7) + 0.01  # nunca por encima de la teórica (0,515): es cota inferior
    assert min_entropia_mcv(b) > h  # MCV no ve la estructura que sí ve la batería


@necesita_binario
def test_markov_con_permanencia_08_da_h_menor_o_igual_04_y_mcv_no_la_ve():
    rng = np.random.default_rng(SEMILLA)
    b = Bits((np.cumsum(rng.random(N) < 0.2) % 2).astype(np.uint8))
    assert EstimadorNist90B().estimar(b) <= 0.4
    assert min_entropia_mcv(b) > 0.9  # el hallazgo R.00-2: MCV es ciega a la dependencia


@necesita_binario
def test_periodica_da_cero():
    b = Bits((np.arange(N) % 8 < 4).astype(np.uint8))
    assert EstimadorNist90B().estimar(b) == pytest.approx(0.0, abs=1e-6)


# ------------------------------------------------------------------ R.02: dónde vive el binario y la muestra


def test_el_binario_por_defecto_ya_no_esta_en_tmp_salvo_que_solo_exista_el_heredado():
    from qrecauda.adaptadores import min_entropia as m

    if not m.BINARIO_EN_CACHE.is_file() and m.BINARIO_HEREDADO.is_file():
        assert m.ubicar_binario() == m.BINARIO_HEREDADO  # compatibilidad con 0.1.0 y la caché antigua
    else:
        assert m.ubicar_binario() == m.BINARIO_EN_CACHE and not str(m.BINARIO_EN_CACHE).startswith("/tmp")


def test_ubicar_binario_prefiere_la_cache_y_cae_al_heredado(tmp_path, monkeypatch):
    from qrecauda.adaptadores import min_entropia as m

    nuevo, viejo = tmp_path / "n" / "ea", tmp_path / "v" / "ea"
    monkeypatch.setattr(m, "BINARIO_EN_CACHE", nuevo)
    monkeypatch.setattr(m, "BINARIO_HEREDADO", viejo)
    assert m.ubicar_binario() == nuevo  # ninguno existe: se indica el nuevo
    viejo.parent.mkdir()
    viejo.write_text("x")
    assert m.ubicar_binario() == viejo
    nuevo.parent.mkdir()
    nuevo.write_text("x")
    assert m.ubicar_binario() == nuevo


def test_un_binario_escribible_por_otros_no_se_ejecuta(tmp_path):
    from qrecauda.adaptadores.min_entropia import verificar_propietario

    b = tmp_path / "ea"
    b.write_text("#!/bin/sh\n")
    b.chmod(0o755)
    verificar_propietario(b)
    b.chmod(0o777)
    with pytest.raises(FuenteNoDisponible, match="escribible"):
        verificar_propietario(b)


def test_un_binario_de_otro_usuario_no_se_ejecuta(tmp_path, monkeypatch):
    import os

    from qrecauda.adaptadores.min_entropia import verificar_propietario

    b = tmp_path / "ea"
    b.write_text("x")
    monkeypatch.setattr(os, "getuid", lambda: 12345)
    if b.stat().st_uid in (12345, 0):
        pytest.skip("el propietario coincide con el uid simulado")
    with pytest.raises(FuenteNoDisponible, match="uid"):
        verificar_propietario(b)


def test_la_muestra_vive_en_un_directorio_0700_y_se_trunca_y_borra(tmp_path, monkeypatch):
    import stat

    from qrecauda.adaptadores import min_entropia as m

    monkeypatch.setattr(m, "DIR_MUESTRA_RAPIDO", tmp_path)
    try:
        with m._muestra_temporal() as f:
            assert f.parent.parent == tmp_path and stat.S_IMODE(f.parent.stat().st_mode) == 0o700
            f.write_bytes(b"secreto")
            guardado = f
            raise RuntimeError("fallo en medio")
    except RuntimeError:
        pass
    assert not guardado.exists() and not guardado.parent.exists()


def test_el_estimador_deja_su_muestra_borrada_y_corre_el_binario_en_su_grupo(tmp_path, monkeypatch):
    """Binario falso: comprueba la ruta de la muestra y que se ejecuta; luego ni el fichero ni el directorio existen."""
    from qrecauda.adaptadores import min_entropia as m

    monkeypatch.setattr(m, "DIR_MUESTRA_RAPIDO", tmp_path / "shm")
    (tmp_path / "shm").mkdir()
    falso = tmp_path / "ea_falso"
    falso.write_text('#!/bin/sh\necho "H_original: 0.75"\n')
    falso.chmod(0o755)
    h = EstimadorNist90B(binario=falso).estimar(Bits(np.zeros(N, dtype=np.uint8)))
    assert h == 0.75 and list((tmp_path / "shm").iterdir()) == []


def test_si_se_agota_el_tiempo_se_mata_el_grupo_y_se_avisa(tmp_path):
    falso = tmp_path / "ea_lento"
    falso.write_text("#!/bin/sh\nsleep 30\n")
    falso.chmod(0o755)
    with pytest.raises(FuenteNoDisponible, match="no pudo ejecutarse"):
        EstimadorNist90B(binario=falso, tiempo_max_s=0.5).estimar(Bits(np.zeros(N, dtype=np.uint8)))
