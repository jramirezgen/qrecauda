"""Los criterios de E1 como funciones puras: cada uno, en su borde, tal como lo fija docs/preinscripciones/E1.md."""

import pytest
from e1_medidas import BUENA, SESGADA, fuente, fuentes_ok, informe

from qrecauda.aplicacion import criterios_e1 as c
from qrecauda.dominio.errores import EntradaInvalida
from qrecauda.dominio.metricas import Metrica


def test_n1_exige_cruda_y_clave_limpias():
    assert c.n1_cumple(informe("C.E1a", 1, cruda=BUENA))
    assert not c.n1_cumple(informe("C.E1a", 1, cruda={**BUENA, "m4": 0.005}))  # runs de la cruda en el borde bajo el umbral
    assert not c.n1_cumple(informe("C.E1a", 1, cruda=BUENA, clave={**BUENA, "m5": 0.01}))  # p = 0,01 NO es > 0,01
    assert not c.n1_cumple(informe("C.E1a", 1, cruda=BUENA, m2=0.9))  # M2 estricto


def test_d1_es_inclusivo_en_la_tolerancia():
    b = informe("C.E1b", 1, cruda={**SESGADA, "m1": 0.0315})
    assert c.d1_cumple(b, 0.03, 0.002)
    assert not c.d1_cumple(informe("C.E1b", 1, cruda={**SESGADA, "m1": 0.0325}), 0.03, 0.002)
    assert not c.d1_cumple(informe("C.E1b", 1, cruda={**SESGADA, "m1": 0.0}), 0.03, 0.002)  # el detector no ve el sesgo


@pytest.mark.parametrize(
    ("cruda", "esperado"),
    [
        (SESGADA, True),
        ({**BUENA, "m1": 0.01}, True),
        ({**BUENA, "m3": 0.01}, True),
        (BUENA, False),
        ({**BUENA, "m4": 0.0, "m5": 0.0}, False),
    ],
    ids=["ambas", "M1 en el umbral", "M3 en el umbral", "ninguna", "solo M4 y M5: no es B1"],
)
def test_b1_es_fallar_m1_o_m3_de_la_cruda(cruda, esperado):
    assert c.b1_cumple(informe("C.E1b", 1, cruda=cruda)) is esperado


def test_m1_decide_por_m1_y_m3_de_la_mitigada_y_no_por_m4_ni_m5():
    """Enmienda 2026-10-07: M4 y M5 de la mitigada son informativas."""
    assert c.m1_cumple(informe("C.E1c", 1, cruda=SESGADA, mitigada={**BUENA, "m4": 0.0, "m5": 0.0}))
    assert not c.m1_cumple(informe("C.E1c", 1, cruda=SESGADA, mitigada={**BUENA, "m1": 0.02}))
    assert not c.m1_cumple(informe("C.E1c", 1, cruda=SESGADA, mitigada={**BUENA, "m3": 0.001}))


def test_m2_exige_las_cinco_en_la_clave():
    assert c.m2_cumple(informe("C.E1c", 1, cruda=SESGADA, mitigada=BUENA))
    for k in ("m1", "m3", "m4", "m5"):
        mala = {**BUENA, k: 0.02 if k == "m1" else 0.0}
        assert not c.m2_cumple(informe("C.E1c", 1, cruda=SESGADA, mitigada=BUENA, clave=mala)), k
    assert not c.m2_cumple(informe("C.E1c", 1, cruda=SESGADA, mitigada=BUENA, m2=0.5))


def test_una_metrica_ausente_es_un_error_no_un_cumple():
    with pytest.raises(EntradaInvalida, match="M4"):
        c.pasan(informe("C.E1a", 1, cruda=BUENA).etapas["cruda"][:2], (Metrica.RUNS,))


PISO, TECHO = 0.8, 0.5  # declaraciones/E1.toml [criterios.c_e1d], enmienda 2026-10-07 (2)


def test_p1_acepta_las_cuatro_fuentes_bien_discriminadas():
    f = {x.fuente: x for x in fuentes_ok(7)}
    assert c.p1_cumple(f, PISO, TECHO) and all(c.p1_detalle(f, PISO, TECHO).values())


def test_p1_acepta_una_ideal_conservadora_del_90b_como_las_medidas():
    """Las 11 medidas reales de la ideal (0,821–0,903) no superan todas 0,9: el 90B de 1 M de bits es conservador, no la fuente."""
    for h in (0.821003, 0.832199, 0.902247):
        f = {x.fuente: x for x in fuentes_ok(7)}
        f["ideal"] = fuente("C.E1d", 7, "ideal", cruda=BUENA, mcv=0.99, h90=h)
        assert c.p1_cumple(f, PISO, TECHO), h


@pytest.mark.parametrize(
    ("nombre", "cambio"),
    [
        ("sesgada", {"cruda": {**SESGADA, "m3": 0.5}}),  # M3 la deja pasar
        ("periodica", {"cruda": BUENA, "h90": 0.95}),  # nada la rechaza
        ("markov", {"cruda": BUENA, "h90": 0.95}),  # el 90B no la rechaza
        ("markov", {"cruda": BUENA, "mcv": 0.5, "h90": 0.17}),  # el MCV ya la rechazaba: no es el hallazgo de la discrepancia 8
        ("ideal", {"cruda": BUENA, "h90": 0.79}),  # bajo el piso calibrado (0,8)
        ("markov", {"cruda": BUENA, "h90": 0.5}),  # techo estricto: 90B < 0,5
        ("periodica", {"cruda": BUENA, "h90": 0.5}),
        ("ideal", {"cruda": {**BUENA, "m5": 0.001}, "h90": 0.95}),
    ],
)
def test_p1_falla_si_una_fuente_no_se_comporta(nombre, cambio):
    f = {x.fuente: x for x in fuentes_ok(7)}
    base = f[nombre]
    cruda = cambio.get("cruda")
    f[nombre] = fuente("C.E1d", 7, nombre, cruda=cruda, mcv=cambio.get("mcv", base.mcv), h90=cambio.get("h90", base.h_90b))
    assert not c.p1_cumple(f, PISO, TECHO) and not c.p1_detalle(f, PISO, TECHO)[nombre]


def test_p1_periodica_basta_con_el_90b_aunque_la_batería_la_deje_pasar():
    f = {x.fuente: x for x in fuentes_ok(7)}
    f["periodica"] = fuente("C.E1d", 7, "periodica", cruda=BUENA, mcv=0.99, h90=0.0)
    assert c.p1_cumple(f, PISO, TECHO)


def test_p1_el_piso_es_inclusivo_y_el_techo_estricto():
    f = {x.fuente: x for x in fuentes_ok(7)}
    f["ideal"] = fuente("C.E1d", 7, "ideal", cruda=BUENA, mcv=0.99, h90=PISO)
    f["markov"] = fuente("C.E1d", 7, "markov", cruda=BUENA, mcv=0.99, h90=0.4999)
    assert c.p1_cumple(f, PISO, TECHO)


def test_p1_exige_un_piso_por_encima_del_techo():
    f = {x.fuente: x for x in fuentes_ok(7)}
    with pytest.raises(EntradaInvalida, match="piso"):
        c.p1_cumple(f, 0.4, 0.5)  # sin hueco no hay separación que medir


def test_p1_exige_las_cuatro_fuentes():
    f = {x.fuente: x for x in fuentes_ok(7)}
    del f["markov"]
    with pytest.raises(EntradaInvalida, match="markov"):
        c.p1_cumple(f, PISO, TECHO)
