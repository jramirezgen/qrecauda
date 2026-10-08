"""QRecauda — pipeline QRNG reproducible en simulador para la recaudación del Perú (TRL 3; sin origen cuántico afirmado).

Capas de fuera hacia dentro (docs/DISENO.md §3; las hace cumplir `.importlinter`):
entrada → api → composicion → adaptadores | presentacion → aplicacion → puertos → datos → dominio.
`transversal` es lo que cruza capas y sólo lo importan entrada y adaptadores.
"""

__version__ = "0.1.0.dev0"

#: de fuera hacia dentro; tests/arquitectura/test_contratos.py comprueba que `.importlinter` dice lo mismo.
CAPAS = ("entrada", "api", "composicion", "adaptadores|presentacion", "aplicacion", "puertos", "datos", "dominio")
