# P.E0 — Parámetros y aritmética de la cadena (fijados antes de medir)

Fecha: 2026-10-07. Valores en `declaraciones/PARAMETROS.toml`; las eurekas los heredan y no los cambian.

## Aritmética (reproducible con una línea de Python, ver el nodo)

| qué | cuenta | resultado |
|---|---|---|
| bits crudos | 8 qubits × 400 000 shots | 3 200 000 |
| rendimiento clave/crudo | medido en la bala trazadora (Peres + Toeplitz, h ≈ 0,995) | ≈ 0,2988 |
| clave | 3,2 M × 0,2988 | ≈ 956 000 bits |
| M2 por bloques | la cota MCV al 99 % exige n ≥ 1288 para superar 0,9 | bloques de 4096 (esperado ≈ 0,943) |
| sesgo máximo que pasa monobit | 2,5758·0,5/√N, N = 800 000 | 0,00144 (7× más estricto que M1 < 0,01) |
| 90B | mínimo de la herramienta | 1 000 000 de bits crudos (se cumple con 3,2 M) |
| secuencias NIST | 956 000 / 10 240 | 93; proporción mínima 0,99 − 3·√(0,0099/93) ≈ 0,958 |

## Reglas

1. Si falta muestra para una prueba, se **suben los shots**; los umbrales no se relajan.
2. **M1 sobre la clave es informativo, no decisivo**: monobit (M3) es más estricto a esta escala. Se reporta, y el veredicto exige las dos.
3. Cada eureka se corre con las **tres semillas** declaradas; el veredicto es sobre las tres, no sobre la mejor. Un fallo no se
   repite con otra semilla: se reporta (selección de semilla prohibida).
4. M1, M3, M4, M5 se miden en tres puntos (cruda, mitigada, clave); el 90B sobre la cruda y la mitigada.
5. Tres niveles de ruido de lectura sintéticos; un cuarto «realista» sólo si `F3.02` confirma el backend falso (⚠️ sin verificar).

## Cómo se revertiría
Si `F3.01` mostrara que 400 000 shots no caben en tiempo razonable, se baja `shots` y se recalcula la tabla; las reglas 1–4 no cambian.
