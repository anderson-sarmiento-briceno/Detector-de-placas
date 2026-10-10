# CLAUDE.md

El contexto completo del proyecto está en [contexto.md](contexto.md). Leerlo antes de cualquier cambio.

- Video de prueba actual: `data/videos/moto_bogota.mp4` (Bogotá, ~2:42, grabación de pantalla comprimida) → `formato_placa: colombia` + `models/detector_colombia.pt`.
- Video anterior: Pexels 4403833 (Taiwán, placas no colombianas) → `formato_placa: generico` + `models/detector_placas.pt`.
- Modo `colombia` acepta carro `ABC123` y moto `ABC12D` (ampliación respecto a contexto.md, pedida por el usuario).
- Los ajustes deben ser reglas generales de Colombia, nunca específicos de las placas de un video.
- Entorno: `.venv` con Python 3.13. Ejecutar: `.venv\Scripts\python -m src.main`.
