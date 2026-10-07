import json

import pytest

from qrecauda.dominio import errores
from qrecauda.dominio.errores import EntradaInvalida, EntropiaInsuficiente, ErrorQRecauda
from qrecauda.entrada import cli
from qrecauda.entrada.codigos import CODIGOS, OK, VEREDICTO_RECHAZADO, codigo_de


def _todas_las_hijas() -> list[type[ErrorQRecauda]]:
    return [c for c in vars(errores).values() if isinstance(c, type) and issubclass(c, ErrorQRecauda)]


def test_cada_error_tiene_codigo_distinto_y_estable():
    assert len(set(CODIGOS.values())) == len(CODIGOS)
    assert codigo_de(EntradaInvalida("x")) == 2
    assert codigo_de(EntropiaInsuficiente("x")) == 3
    assert codigo_de(ErrorQRecauda("x")) == 10


def test_ninguna_excepcion_del_dominio_queda_sin_su_codigo():
    """Una hija nueva sin fila en la tabla caería en el 10 genérico en silencio."""
    sin = [c.__name__ for c in _todas_las_hijas() if c not in CODIGOS]
    assert not sin, f"faltan en entrada/codigos.py: {sin}"
    assert OK not in CODIGOS.values() and VEREDICTO_RECHAZADO not in CODIGOS.values()


@pytest.mark.parametrize("clase", _todas_las_hijas(), ids=lambda c: c.__name__)
def test_la_cli_devuelve_el_codigo_de_cada_excepcion(clase, monkeypatch, capsys):
    def falla(cfg):
        raise clase("provocado")

    monkeypatch.setattr(cli.api, "generar_clave", falla)
    assert cli.main([]) == CODIGOS[clase]
    salida = capsys.readouterr()
    assert clase.__name__ in salida.err and not salida.out  # el error va a stderr


@pytest.mark.parametrize("clase", _todas_las_hijas(), ids=lambda c: c.__name__)
@pytest.mark.parametrize("orden", [["correr", "declaraciones/E1.toml"], ["juzgar", "E1"]], ids=["correr", "juzgar"])
def test_correr_y_juzgar_devuelven_el_codigo_de_cada_excepcion(clase, orden, monkeypatch, capsys):
    def falla(*a, **k):
        raise clase("provocado")

    monkeypatch.setattr(cli.api, orden[0], falla)
    assert cli.main(orden) == CODIGOS[clase]
    salida = capsys.readouterr()
    assert clase.__name__ in salida.err and not salida.out


def test_corrida_invalida_es_el_codigo_9():
    """Fijo: los scripts y el DAG distinguen «corrida inválida» de «veredicto rechazado» (1) por este número."""
    assert CODIGOS[errores.CorridaInvalida] == 9 and codigo_de(errores.CorridaInvalida("x")) == 9


def _config(tmp_path, texto="backend = 'prng'\nshots = 20000\nqubits = 8\n"):
    ruta = tmp_path / "c.toml"
    ruta.write_text(texto)
    return str(ruta)


def test_corrida_aprobada_sale_con_cero_y_tabla(tmp_path, capsys):
    assert cli.main(["--config", _config(tmp_path)]) == OK
    assert "VEREDICTO: APROBADO" in capsys.readouterr().out


def test_formato_json_es_canonico_y_parseable(tmp_path, capsys):
    assert cli.main(["--config", _config(tmp_path), "--formato", "json"]) == OK
    texto = capsys.readouterr().out.strip()
    d = json.loads(texto)
    assert d["aprobado"] is True and texto == json.dumps(d, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def test_configuracion_invalida_y_backend_sin_adaptador_tienen_su_codigo(tmp_path, capsys):
    assert cli.main(["--config", _config(tmp_path, "shotz = 1")]) == CODIGOS[EntradaInvalida]
    capsys.readouterr()
    token = tmp_path / "t.txt"
    token.write_text("x")
    cfg = _config(tmp_path, f"backend = 'ibm'\nibm_token_ruta = '{token}'\n")
    assert cli.main(["--config", cfg]) == CODIGOS[errores.FuenteNoDisponible]
