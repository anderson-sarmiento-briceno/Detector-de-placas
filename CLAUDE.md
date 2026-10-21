# CLAUDE.md

El contexto completo del proyecto está en [contexto.md](contexto.md). Leerlo antes de cualquier cambio.

- Video de prueba actual: `data/videos/moto_bogota_2.mp4` (Bogotá, ~2:08, grabación de pantalla comprimida) → `formato_placa: colombia` + `models/detector_colombia_v4.pt` + OCR `models/ocr_colombia.onnx`.
- `data/videos/bogota_trafico_4k.mp4` (71 min, 4K): frames de entrenamiento 0–3670 s; los últimos 10 min (desde 3684 s) son solo PRUEBA.
- `data/videos/bogota_trafico_4k_v2.mp4` (30 min, 4K, día): usado para el OCR (scripts/recortes_ocr_video.py); el tramo 590–910 s (min 10–15, clip `prueba_v2_5min.mp4`) es solo PRUEBA.
- `data/videos/bogota_trafico_4k_nocturna.mp4` (14,8 min, 1080p, NOCHE, grabado desde moto): entrenamiento 0–700 s; desde 710 s es solo PRUEBA.
- Los videos se pueden borrar de data/videos: los frames, recortes y revisiones quedan en data/datasets/.
- Modelos oficiales: detector `models/detector_colombia_v4.pt` (día + noche), OCR `models/ocr_colombia.onnx` (xs_v3, día + noche; respaldos `ocr_colombia_v2.onnx`, `ocr_colombia_v1.onnx`). Un modelo nuevo solo se adopta si no empeora en las pruebas de día.
- Entrenar el detector: doble clic en `entrenar_detector.bat` (ventana visible; si se corta, al reabrirlo continúa). Partir del detector original (`models/detector_colombia.pt`), no de uno ya afinado: afinar v1 con el ritmo por defecto lo empeoró (v2).
- Al editar archivos desde PowerShell 5 no usar `Set-Content -Encoding UTF8` (agrega BOM y rompe config.yaml), ni `Get-Content`/`Set-Content` sobre archivos con tildes (las daña). Editar con la herramienta Edit o con Python.
- FASE 2 – App Android (Flutter) en `app/`: modelos ONNX en `app/assets/models` (copias de `models/movil/`: detector v4 exportado con `nms=True`, OCR v3). Lógica traducida de Python en `app/lib/placas.dart` y `votacion.dart` (mismas pruebas en `app/test`). Compilar: `cd app; flutter build apk --release` (Flutter en `C:\src\flutter`, JDK 17, SDK Android en `%LOCALAPPDATA%\Android\Sdk`). APK para el usuario en `outputs/app/`. Si se reentrena un modelo, volver a exportarlo a `models/movil/` y copiarlo a `app/assets/models`.
- `data/videos/18-24-05_completo.mp4` (17,6 min) contiene a moto_bogota_2 en sus primeros 2:10: ese tramo es solo de PRUEBA; para entrenar se usa desde 2:20.
- Objetivo: app móvil (Android + iOS), cero gastos. Modelos entrenados por nosotros: detector (scripts/entrenar_detector.py) y OCR (fast-plate-ocr, scripts/exportar_ocr.py).
- Video anterior: Pexels 4403833 (Taiwán, placas no colombianas) → `formato_placa: generico` + `models/detector_placas.pt`.
- Modo `colombia` acepta carro `ABC123` y moto `ABC12D` (ampliación respecto a contexto.md, pedida por el usuario).
- Los ajustes deben ser reglas generales de Colombia, nunca específicos de las placas de un video.
- Entorno: `.venv` con Python 3.13. Ejecutar: `.venv\Scripts\python -m src.main`.
