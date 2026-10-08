# Seguridad

## Alcance

QRecauda es un prototipo de investigación (TRL 3). No es una librería criptográfica certificada y no debe protegerse con ella ningún dato real.

- Los bits que produce el simulador son seudoaleatorios. No hay origen cuántico afirmado.
- No tiene certificación FIPS 140-3, Common Criteria ni evaluación de laboratorio. Las pruebas NIST SP 800-22 y la estimación SP 800-90B son comprobaciones estadísticas, no certificaciones.
- No incluye gestión de claves (KMS o HSM), protección del canal ni anti-replay. El registro de nonces vive en la memoria del proceso.
- La clave se dimensiona con min-entropía MCV, que supone bits independientes. Con una fuente correlacionada la longitud se sobrestima.

El modelo de amenazas y las limitaciones conocidas están en [`docs/AMENAZAS.md`](docs/AMENAZAS.md). Si necesitas una fuente de claves para producción, usa una librería criptográfica auditada y el generador del sistema operativo.

## Qué sí es un problema de seguridad

- Un fallo que permita reutilizar un par (clave, nonce) en AES-GCM.
- Una ruta por la que un secreto (token de IBM, clave generada) se imprima, se registre o se escriba en el repo.
- Una dependencia con una vulnerabilidad conocida que el proyecto expone.
- Una debilidad en el dimensionado de la clave que no esté ya listada en `docs/AMENAZAS.md`.

Que el simulador no aporte entropía cuántica ya está documentado y no es una vulnerabilidad nueva.

## Cómo reportar

Usa el reporte privado de vulnerabilidades de GitHub: pestaña Security del repositorio, «Report a vulnerability». Si no está disponible, abre una incidencia que diga solo que tienes un reporte de seguridad, sin detalles, y te indicaremos un canal privado.

Incluye la versión, los pasos para reproducir y el efecto esperado. Es un proyecto mantenido por una persona: no hay plazo garantizado de respuesta. Solo la versión 0.1.0 recibe correcciones.
