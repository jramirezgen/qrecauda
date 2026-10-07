from qrecauda.dominio.metricas import Metrica, Veredicto, medir


def test_desigualdad_estricta_en_el_umbral():
    assert not medir(Metrica.MONOBIT, 0.01).cumple  # «p-value > 0,01»
    assert medir(Metrica.MONOBIT, 0.0101).cumple
    assert not medir(Metrica.LATENCIA, 500.0).cumple  # «< 500 ms»


def test_veredicto_conjuntivo_y_vacio_no_aprueba():
    assert not Veredicto(()).aprobado
    v = Veredicto((medir(Metrica.MONOBIT, 0.5), medir(Metrica.RUNS, 0.001)))
    assert not v.aprobado and v.fallos() == (Metrica.RUNS,)
