import pytest

from qrecauda.dominio.bits import Bits
from qrecauda.dominio.muestra import Muestra, Origen, Procedencia

B = Bits.desde([0, 1, 0, 1])


def test_hardware_sin_job_id_no_se_construye():
    with pytest.raises(ValueError, match="job_id"):
        Muestra(B, Origen.HARDWARE_IBM, 1, 4)
    ok = Muestra(B, Origen.HARDWARE_IBM, 1, 4, procedencia=Procedencia("ibm_x", "job-1", "qiskit 2.5.2"))
    assert ok.reclama_origen_cuantico


def test_una_mitigacion_que_remuestrea_degrada_el_origen():
    hw = Muestra(B, Origen.HARDWARE_IBM, 1, 4, procedencia=Procedencia("ibm_x", "job-1"))
    remuestreada = hw.mitigada_con(B, conserva_bits_por_disparo=False)
    assert remuestreada.origen is Origen.PRNG_CLASICO and not remuestreada.reclama_origen_cuantico and remuestreada.mitigada
    assert hw.mitigada_con(B, conserva_bits_por_disparo=True).reclama_origen_cuantico
