"""Congela las firmas de la fachada pública: cambiarlas es un cambio de versión, no un descuido."""

import inspect

from qrecauda import api


def test_firmas_congeladas():
    assert sorted(api.__all__) == ["Configuracion", "Resultado", "generar_clave"]
    assert str(inspect.signature(api.generar_clave)) == "(cfg: 'Configuracion') -> 'Resultado'"
