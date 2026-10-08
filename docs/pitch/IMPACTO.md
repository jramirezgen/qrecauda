# Cifras de impacto y su fuente

Consulta del 2026-10-08. Etiqueta **verificado**: la página se abrió y la cifra figura en ella. Etiqueta **tercero**: la
cifra viene de la fuente citada y no se contrastó con una segunda. Ninguna cifra de esta tabla sale de una corrida de
QRecauda; son contexto. Los enlaces deben reabrirse antes de publicar cualquier material que los cite.

| dato | cifra | fuente | etiqueta |
|---|---|---|---|
| Metro de Lima, L1 | 203,9 millones de pasajeros en 2025 (récord) | <https://energiminas.com/?p=48912> (dato de 2025, publicado el 2026-07-17) | verificado |
| Metro de Lima, L1 | más de 191 millones de pasajeros en 2024; más de 600 000 usuarios por día | <https://energiminas.com/2025/03/10/linea-1-del-metro-transportaria-212-millones-de-pasajeros-este-ano-11-mas-que-2024> | tercero |
| Metro de Lima, L2 | gratuita y en marcha blanca: no genera tarifa, no sirve como cifra de recaudación | infobae, 2025-09-19 | tercero |
| Peajes, tráfico | 24,6 millones de vehículos en el primer cuatrimestre de 2021; es el único dato nacional hallado, está desactualizado y no trae recaudación | <https://andina.pe/agencia/noticia-ositran-trafico-vehicular-crece-24-carreteras-concesionadas-852013.aspx> | tercero |
| OSITRAN | supervisa contratos de concesión y revisa tarifas (OCDE, 2020); no se halló un rol suyo en el telepeaje | <https://oecd.org/es/publications/2020/02/driving-performance-at-peru-s-transport-infrastructure-regulator_70f55b37/full-report/component-5.html> | tercero |
| MTC | concedente de las APP; regula el telepeaje en el Reglamento Nacional de Tránsito (lectura de placa, no criptografía) | gestion.pe; andina.pe | tercero |
| Ley 29733 | el DS 016-2024-JUS (publicado el 2024-11-30) reemplaza al DS 003-2013-JUS y exige medidas técnicas de seguridad; no exige un QRNG | <https://www.gob.pe/institucion/anpd/normas-legales/6554453-16-2024-jus> | tercero |
| SBS | Res. 504-2021 (seguridad de la información y ciberseguridad), sólo sistema financiero; no se halló un requisito concreto de criptografía | cms.law | tercero |
| NIST SP 800-90C | versión final del 2025-09-25 | <https://csrc.nist.gov/News/2025/nist-publishes-sp-800-90c> | verificado |
| NIST SP 800-90B | versión final de 2018-01; norma de fuentes de entropía | csrc.nist.gov | tercero |
| NIST SP 800-22 | en 2022-04 NIST decidió revisarla y aclaró que no sirve para evaluar generadores aleatorios criptográficos | <https://csrc.nist.gov/News/2022/decision-to-revise-nist-sp-800-22-rev-1a> | tercero |
| ID Quantique | chips QRNG con validación NIST ESV (certificado E63, por la vía IID de 90B) | <https://csrc.nist.gov/projects/cryptographic-module-validation-program/entropy-validations/certificate/63> | tercero |
| Aleatoriedad certificada con hardware | Nature 640, 343-348 (2025-03-26), Quantinuum H2, 71 313 bits certificados | <https://doi.org/10.1038/s41586-025-08737-1> | tercero |
| QRNG de IBM certificado | no se encontró | n/d | no encontrado |

Advertencias de uso:

- Ni la Ley 29733, ni la SBS ni el MTC exigen un QRNG. No se afirma.
- El argumento de entropía se apoya en NIST SP 800-90B y 800-90C, no en SP 800-22.
- Aer con semilla es determinista: sin valor de seguridad.
