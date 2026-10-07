"""Excepción raíz del proyecto y sus hijas con nombre. La tabla de códigos de salida vive en entrada/codigos.py."""


class ErrorQRecauda(Exception):
    """Raíz: todo fallo esperado del proyecto la hereda; `except Exception` silencioso está prohibido."""


class EntradaInvalida(ErrorQRecauda):
    """Un dato que llega de fuera (bits, configuración, semilla) no cumple su contrato."""


class EntropiaInsuficiente(ErrorQRecauda):
    """La min-entropía medida no alcanza para extraer ni un bit con el parámetro de seguridad pedido."""


class FuenteNoDisponible(ErrorQRecauda):
    """El backend cuántico (o su simulador) no pudo entregar una muestra."""


class EsquemaFuturo(ErrorQRecauda):
    """Un artefacto declara un esquema más nuevo que el que este lector entiende."""
