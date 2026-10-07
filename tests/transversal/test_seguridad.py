import pytest

from qrecauda.dominio.errores import EntradaInvalida
from qrecauda.transversal.seguridad import Secreto, describir, leer_secreto


def test_lee_por_ruta_y_recorta(tmp_path):
    f = tmp_path / "t.txt"
    f.write_text("  valor-secreto \n")
    assert leer_secreto(f) == "valor-secreto"


@pytest.mark.parametrize("contenido", [None, "", "  \n"])
def test_ausente_o_vacio_aborta_sin_citar_contenido(tmp_path, contenido):
    f = tmp_path / "t.txt"
    if contenido is not None:
        f.write_text(contenido)
    with pytest.raises(EntradaInvalida):
        leer_secreto(f)


def test_describir_no_muestra_el_valor():
    assert "abc123" not in describir("abc123")
    assert "6" in describir("abc123")


def test_secreto_no_se_filtra_por_repr_str_ni_format():
    s = Secreto("abc123")
    for texto in (repr(s), str(s), f"{s}", f"{s}"):
        assert "abc123" not in texto
    assert s.revelar() == "abc123"


def test_secreto_desde_ruta(tmp_path):
    f = tmp_path / "t.txt"
    f.write_text("abc123\n")
    assert Secreto.desde_ruta(f).revelar() == "abc123"
