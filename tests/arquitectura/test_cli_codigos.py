from qrecauda.dominio.errores import EntradaInvalida, EntropiaInsuficiente, ErrorQRecauda
from qrecauda.entrada.codigos import CODIGOS, codigo_de


def test_cada_error_tiene_codigo_distinto_y_estable():
    assert len(set(CODIGOS.values())) == len(CODIGOS)
    assert codigo_de(EntradaInvalida("x")) == 2
    assert codigo_de(EntropiaInsuficiente("x")) == 3
    assert codigo_de(ErrorQRecauda("x")) == 10
