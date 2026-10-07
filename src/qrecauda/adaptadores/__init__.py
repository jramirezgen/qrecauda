"""Adaptadores: implementan UN puerto cada uno, traducen su SDK al dominio y no se importan entre sí (C2).
`ruido` y `transpilacion` viven DENTRO del paquete `aer`, que es un solo adaptador.

| módulo        | puerto        | SDK            | estado                                  |
|---------------|---------------|----------------|-----------------------------------------|
| prng          | FuenteDeBits  | numpy          | hecho (línea base del pitch)            |
| estadistica   | Validador     | scipy          | hecho (M1, M3, M4, M5)                  |
| aer           | FuenteDeBits  | qiskit-aer     | DAG F3.01                               |
| aer/ruido     | (modelo)      | qiskit-aer     | DAG F3.02, dentro del paquete `aer`     |
| mthree        | Mitigador     | mthree         | DAG F4.01 (spike S.02 antes)            |
| ibm_runtime   | FuenteDeBits  | qiskit-ibm-rt  | DAG F3.04 (opcional: hardware real)     |
| nist          | Validador     | nistrng        | DAG F5.01 (contrasta a `estadistica`)   |
| aer/transpilacion | (paso de aer) | qiskit-ibm-tr | DAG F3.03; ibm_runtime la recibe inyectada |
| zne_pec       | EstimadorDeSesgo | qiskit-aer  | DAG F4.02 (ZNE/PEC sobre ⟨Z⟩; D-003)    |
| min_entropia  | Validador     | numpy          | DAG F5.02 (contrasta con dominio/MCV)   |
| almacen_json  | Almacen       | stdlib         | DAG F2.06                               |
| aes_gcm       | Cifrador      | cryptography   | DAG F6.01                               |
| sonda_local   | SondaDeMaquina | stdlib        | DAG C.E3 (carga, CPU, máquina)          |
"""
