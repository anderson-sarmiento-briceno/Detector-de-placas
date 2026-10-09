# Contexto del proyecto: Lector de placas desde casco de moto

## Objetivo general
Sistema que lee placas de carros **desde atrás**, usando una cámara montada en el casco de un motociclista. Cada placa leída se compara contra una base de datos de placas de interés y, si hay coincidencia, se genera una **alerta**.

## Fase actual: FASE 1 (prototipo offline)
- Entrada: **un video ya grabado** (mp4) en lugar de la cámara en vivo.
- Salida: detectar las placas en el video, leer sus caracteres (OCR), comparar con una BD local y mostrar alerta cuando coincidan.
- Todo corre en un PC (Windows/Linux) con Python, desarrollado en VS Code con Claude Code.
- NO hay todavía hardware de casco, ni streaming, ni app móvil. No sobre-diseñar para eso, pero mantener el código modular para poder cambiar la fuente de video después.

## Video de prueba inicial (empezamos por aquí)
- Video: **"Footage of a busy road from a moving vehicle"** de Pexels (gratis, licencia Pexels).
  - Página: https://www.pexels.com/video/footage-of-a-busy-road-from-a-moving-vehicle-4403833/
  - Descarga directa: https://www.pexels.com/download/video/4403833/
- Guardarlo como: `data/videos/pexels_4403833.mp4`.
- Por qué este: está grabado desde un vehículo en movimiento, lo más parecido a la vista desde el casco.
- **Importante: las placas de este video NO son colombianas.** Por eso, mientras usemos este video:
  - La validación con el formato colombiano (`ABC123`) debe poder **desactivarse** desde `config.yaml` (`formato_placa: generico`).
  - En modo `generico`: aceptar textos alfanuméricos de 5 a 8 caracteres, sin la corrección letra/número por posición.
  - En modo `colombia`: aplicar regex `^[A-Z]{3}[0-9]{3}$` + corrección por posición (ver más abajo).
- Para probar la alerta: después de una primera corrida, tomar 2 o 3 placas que el sistema haya leído bien en `outputs/lecturas.csv`, cargarlas en la BD con `scripts/cargar_placas.py` y volver a correr; deben salir las alertas.
- Primer objetivo concreto: que el detector encuentre las placas en este video y dibuje las cajas. El OCR va después.
- Luego pasaremos a videos con placas colombianas (p. ej. POV en moto por Bogotá) y activaremos `formato_placa: colombia`.

### config.yaml inicial esperado
```yaml
video: data/videos/pexels_4403833.mp4
formato_placa: generico        # generico | colombia
procesar_cada_n_frames: 2
confianza_minima_deteccion: 0.4
votos_minimos_para_confirmar: 3
mostrar_ventana: true
guardar_video_salida: true
ruta_bd: data/placas.db
ruta_log: outputs/lecturas.csv
modelo_detector: models/detector_placas.pt
```

## Stack técnico
- **Python 3.10+** con entorno virtual (`.venv`).
- **OpenCV** (`opencv-python`): lectura del video, dibujo de cajas, visualización.
- **Ultralytics YOLO** (`ultralytics`): detección de la placa dentro del frame.
  - Para el video de Pexels (placas extranjeras) usar un detector de placas genérico preentrenado (YOLO de placas de licencia, cualquier país).
  - Cuando pasemos a video colombiano: modelo para placas colombianas (p. ej. `Rotsen2/detector-placas-colombia` en Hugging Face, YOLOv8n) o entrenar uno propio con datasets de Roboflow Universe (`placa_colombia`, `placas-colombia`).
- **OCR**: empezar con `easyocr` (simple). Alternativas si la precisión es baja: `paddleocr` o `fast-plate-ocr`.
- **Base de datos**: SQLite (`sqlite3` de la librería estándar). Para pruebas rápidas también se acepta un CSV.
- Sin servicios en la nube en esta fase: todo local.

## Formato de placas en Colombia (importante para validar el OCR)
- Carros: **3 letras + 3 números** → `ABC123`. Regex: `^[A-Z]{3}[0-9]{3}$`.
- Motos (fuera de alcance por ahora): `ABC12D`.
- Colores: amarilla con letras negras (particular), blanca con letras negras (servicio público); existen otros colores para oficiales/diplomáticos.
- La placa suele incluir el nombre del municipio en la parte inferior: **ignorar ese texto**, solo interesa la línea grande de 6 caracteres.
- Normalizar siempre: mayúsculas, sin espacios, sin guiones (`ABC-123` → `ABC123`).

### Corrección de errores típicos del OCR por posición
Como las 3 primeras posiciones son letras y las 3 últimas son números, corregir confusiones según la posición:
- En posiciones de **letra**: `0→O`, `1→I`, `5→S`, `8→B`, `2→Z`, `6→G`, `4→A`.
- En posiciones de **número**: `O→0`, `D→0`, `Q→0`, `I→1`, `L→1`, `S→5`, `B→8`, `Z→2`, `G→6`, `A→4`.
- Si después de corregir no cumple el regex, descartar la lectura.

## Pipeline esperado (Fase 1)
1. Abrir el video con OpenCV y procesar frame por frame (opción de saltar frames, p. ej. procesar 1 de cada N, para ir más rápido).
2. Detectar placas con YOLO → bounding boxes con confianza mínima configurable.
3. Recortar cada placa (con un pequeño margen) y preprocesar: escala de grises, redimensionar, mejorar contraste (CLAHE), opcionalmente binarizar.
4. OCR sobre el recorte → texto crudo.
5. Normalizar y validar según `formato_placa` (en `colombia`: corregir por posición + regex; en `generico`: solo alfanumérico de 5 a 8 caracteres).
6. **Votación temporal**: la misma placa aparece en varios frames seguidos; acumular lecturas (por tracking de YOLO o por cercanía de cajas) y confirmar el texto más votado solo cuando aparezca al menos K veces. Esto reduce falsos positivos.
7. Comparar la placa confirmada contra la BD.
8. Si coincide: alerta (mensaje en consola + caja roja en el video + sonido opcional) y registrar el evento.
9. Guardar log de todas las lecturas (CSV): timestamp del video, número de frame, placa, confianza, si hubo coincidencia.
10. Opción de guardar un video de salida con las cajas y textos dibujados.

## Estructura de carpetas propuesta
```
lector-placas/
├── contexto.md            # este archivo
├── CLAUDE.md              # apunta a contexto.md para Claude Code
├── requirements.txt
├── config.yaml            # rutas, umbrales, cada cuántos frames, etc.
├── data/
│   ├── videos/            # videos de prueba (no subir a git)
│   └── placas.db          # BD SQLite con placas de interés
├── models/                # pesos YOLO (.pt)
├── outputs/               # videos procesados y logs CSV
├── src/
│   ├── main.py            # punto de entrada: python -m src.main --video ruta.mp4
│   ├── video_source.py    # abstracción de la fuente (archivo hoy, cámara mañana)
│   ├── detector.py        # detección YOLO
│   ├── ocr.py             # OCR + preprocesado del recorte
│   ├── plate_utils.py     # normalización, corrección por posición, regex
│   ├── tracker.py         # votación temporal de lecturas
│   ├── database.py        # acceso a la BD (consultar, cargar placas)
│   └── alerts.py          # cómo se notifica una coincidencia
├── scripts/
│   └── cargar_placas.py   # cargar placas desde CSV a la BD
└── tests/
    └── test_plate_utils.py
```

## Base de datos (esquema inicial)
```sql
CREATE TABLE placas_interes (
    placa       TEXT PRIMARY KEY,   -- normalizada, ej. ABC123
    motivo      TEXT,               -- descripción libre
    creado_en   TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE detecciones (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    video       TEXT,
    frame       INTEGER,
    segundo     REAL,
    placa       TEXT,
    confianza   REAL,
    coincidencia INTEGER            -- 0/1
);
```
- Las consultas deben ser por igualdad exacta sobre la placa normalizada.
- (Futuro) Considerar coincidencia aproximada (distancia de 1 carácter) como "posible coincidencia" con menor prioridad.

## Retos conocidos del caso de uso (tenerlos en cuenta desde ya)
- Cámara en casco = **movimiento, vibración y desenfoque**: conviene elegir, dentro de la secuencia, el frame más nítido (varianza del Laplaciano) para el OCR.
- Distancia y ángulo variables: placas pequeñas o inclinadas; permitir umbral de tamaño mínimo de caja.
- Luz: contraluz, noche, reflejos sobre la placa.
- Placas sucias, dobladas o parcialmente tapadas (portaplacas, bicicletas, remolques).
- Rendimiento: el objetivo final es tiempo real en un dispositivo pequeño, así que preferir modelos livianos (YOLO nano) y medir FPS.

## Criterios de "listo" para la Fase 1
- `python -m src.main --video data/videos/pexels_4403833.mp4` procesa el video sin errores.
- Muestra en pantalla las placas detectadas con su texto.
- Si una placa del video está en la BD, se ve la alerta en consola y en el video.
- Se genera `outputs/lecturas.csv` y (opcional) `outputs/video_procesado.mp4`.
- Tests unitarios de `plate_utils` pasan para ambos modos (`generico` y `colombia`).

## Fases futuras (no implementar todavía)
- Fase 2: fuente en vivo (webcam / cámara IP / cámara de acción por RTSP).
- Fase 3: ejecución en dispositivo embebido (Raspberry Pi 5, Jetson o celular) y alerta al motociclista (sonido en el casco / vibración / app).
- Fase 4: BD central sincronizada, registro con GPS de dónde se vio la placa.

## Consideraciones legales y de privacidad
- Las placas y su ubicación son datos personales (Ley 1581 de 2012 – Habeas Data en Colombia). Guardar solo lo necesario, proteger la BD y definir quién tiene acceso y con qué propósito.
- Los videos de prueba descargados de internet son solo para desarrollo local; respetar su licencia.

## Convenciones de código
- Código y comentarios en **español** (nombres de variables pueden ir en inglés si es más natural).
- Funciones pequeñas y con type hints; `logging` en lugar de `print` para depuración.
- Toda configuración (rutas, umbrales, N de frames) en `config.yaml`, nada "quemado" en el código.
- No subir videos, pesos de modelos ni la BD a git (`.gitignore`).

## Cómo quiero que me ayude Claude Code
- Ir paso a paso, probando siempre con `data/videos/pexels_4403833.mp4`:
  1. Esqueleto del proyecto, `requirements.txt` y `config.yaml`.
  2. Leer el video y mostrarlo frame a frame (`video_source.py`).
  3. Detectar placas y dibujar cajas (`detector.py`).
  4. OCR sobre los recortes (`ocr.py`) en modo `generico`.
  5. Votación temporal, BD y alertas.
- Explicar brevemente qué hace cada parte nueva y cómo probarla.
- Antes de cambios grandes de arquitectura, proponer y esperar confirmación.
