import pytest

from qrecauda.dominio.errores import EntradaInvalida
from qrecauda.transversal.configuracion import Configuracion


def test_clave_desconocida_aborta():
    with pytest.raises(EntradaInvalida):
        Configuracion.desde_mapa({"shotz": 10})


def test_ibm_exige_ruta_del_token():
    with pytest.raises(EntradaInvalida):
        Configuracion(backend="ibm")
