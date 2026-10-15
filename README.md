# Valencia, tu plan: datos

Datos de la app **Valencia, tu plan**, una agenda gratuita de música, teatro y otras
actividades culturales de Valencia, con enlace directo a la web donde se compran las entradas.

## Aviso de derechos

© 2026 Valencia, tu plan. Todos los derechos reservados.

- El código de la aplicación y de los programas de actualización, el diseño, el logotipo, los
  textos propios y la forma de seleccionar, organizar y presentar los eventos pertenecen al
  titular. No se concede ninguna licencia de uso, copia, modificación ni redistribución.
- Queda prohibida la copia, extracción o reutilización sistemática o sustancial de `eventos.json`
  y del resto de datos de este repositorio sin permiso previo por escrito.
- Los datos de cada evento (título, fecha, hora, precio) proceden de las salas y organizadores,
  que conservan sus derechos sobre ellos. Los nombres y marcas de salas, artistas y plataformas
  de venta pertenecen a sus titulares.
- La información es orientativa. Confirma siempre fecha, hora, precio y disponibilidad en la
  web de venta.

Para pedir permiso, o para solicitar la corrección o retirada de un dato: [correo electrónico].

## Cómo funciona

Cada lunes, un programa automático (GitHub Actions) consulta las webs de las salas y actualiza
`eventos.json`. La app lee ese archivo cada vez que se abre.
