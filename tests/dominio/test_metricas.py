from qrecauda.dominio.metricas import Metrica, Veredicto, medir


def test_desigualdad_estricta_en_el_umbral():
    assert not medir(Metrica.MONOBIT, 0.01).cumple  # «p-value > 0,01»
    assert medir(Metrica.MONOBIT, 0.0101).cumple
    assert not medir(Metrica.LATENCIA, 500.0).cumple  # «< 500 ms»


def test_veredicto_conjuntivo_y_vacio_no_aprueba():
    assert not Veredicto(()).aprobado
    v = Veredicto((medir(Metrica.MONOBIT, 0.5), medir(Metrica.RUNS, 0.001)))
    assert not v.aprobado and v.fallos() == (Metrica.RUNS,)


def test_la_calidad_de_clave_exige_las_cinco_metricas_presentes():
    """A-2: una métrica ausente no aprueba (antes bastaba con que las presentes cumplieran)."""
    from qrecauda.dominio.metricas import METRICAS_DE_CLAVE

    todas = [medir(m, {Metrica.SESGO: 0.001, Metrica.MIN_ENTROPIA: 0.99}.get(m, 0.5)) for m in METRICAS_DE_CLAVE]
    assert Veredicto(tuple(todas)).calidad_de_clave_aprobada
    assert not Veredicto((medir(Metrica.MONOBIT, 0.5),)).calidad_de_clave_aprobada
    for ausente in METRICAS_DE_CLAVE:
        resto = tuple(x for x in todas if x.metrica is not ausente)
        assert not Veredicto(resto).calidad_de_clave_aprobada, ausente
