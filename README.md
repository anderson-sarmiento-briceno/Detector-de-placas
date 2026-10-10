# 🏍️ Lector de placas desde casco de moto

Sistema de reconocimiento automático de placas vehiculares (ALPR) pensado para una cámara montada en el casco de un motociclista. Lee las placas de los carros **desde atrás**, las compara contra una base de datos de placas de interés y genera una **alerta** cuando hay coincidencia.

> **Fase 1 – prototipo offline:** procesa videos ya grabados (`.mp4`) en un PC. Todo corre en local, sin servicios en la nube.

---

## ✨ Características

- 🎯 **Detección de placas** con YOLOv11 nano (liviano, pensado para dispositivos pequeños).
- 🔤 **Lectura de caracteres (OCR)** con EasyOCR, con preprocesado (escala de grises, escalado y CLAHE).
- 🇨🇴 **Validación de formato colombiano** (`ABC123`) con corrección automática de confusiones típicas del OCR según la posición (`8→B`, `O→0`, …), o modo **genérico** para placas de otros países.
- 🗳️ **Votación temporal**: cada vehículo se sigue entre frames y sus lecturas se votan carácter por carácter; aunque el OCR nunca lea la placa completa igual, se confirma una sola placa.
- 🗄️ **Base de datos SQLite** de placas de interés.
- 🚨 **Alertas** en consola y en el video (caja roja) cuando una placa coincide.
- 📄 **Registro CSV** de todas las lecturas y **video de salida** anotado.
- 🔌 **Fuente de video intercambiable**: hoy un archivo, mañana una cámara en vivo.

---

## 🧭 Cómo funciona

```
                          por cada frame
 video.mp4 ──► Fuente ──► Detector ──► OCR ──► Validación ──► Votación ──► ¿En la BD? ──► 🚨 Alerta
               de video   (YOLO)       (EasyOCR) (formato)    temporal       (SQLite)
                             │            │                                      │
                          cajas de     texto de                             log CSV +
                          placas       la placa                           video anotado
```

1. **Fuente de video**: lee el video frame a frame (puede saltar frames para ir más rápido).
2. **Detector**: YOLO encuentra los rectángulos donde hay placas.
3. **OCR**: recorta cada placa, mejora la imagen y lee el texto.
4. **Validación**: normaliza el texto (`abc-123` → `ABC123`) y verifica el formato.
5. **Votación temporal**: el seguimiento de YOLO (ByteTrack) identifica cada vehículo entre frames; sus lecturas se votan **carácter por carácter** y se confirma una sola placa.
6. **Consulta**: busca la placa confirmada en la base de datos.
7. **Alerta**: si coincide, avisa en consola, la marca en rojo en el video y registra el evento.

---

## 📦 Requisitos

- Python **3.10+** (probado con 3.13)
- Windows o Linux
- GPU NVIDIA opcional (sin GPU corre en CPU a ~10 FPS)

---

## 🚀 Instalación

```powershell
git clone https://github.com/anderson-sarmiento-briceno/Detector-de-placas.git lector_placas
cd lector_placas

# Entorno virtual
python -m venv .venv
.venv\Scripts\activate            # Linux/Mac: source .venv/bin/activate

# Dependencias
pip install -r requirements.txt

# Descargar los detectores de placas (≈6 MB cada uno)
python -m scripts.descargar_modelo --modelo colombia   # placas colombianas (por defecto en config.yaml)
python -m scripts.descargar_modelo                     # genérico, placas de otros países
```

> Los modelos de EasyOCR (≈95 MB) se descargan automáticamente la primera vez que se ejecuta el programa.

---

## ▶️ Uso

### 1. Procesar videos

Copiar los videos (`.mp4`, `.avi`, `.mov`, `.mkv`…) en `data/videos/` y ejecutar:

```powershell
python -m src.main                                  # todos los videos de data/videos
python -m src.main --video data/videos/ruta.mp4     # un solo video
```

En consola sale cada placa confirmada y, al final, un resumen por video:

```
✅ Placa confirmada CTB816  (vehículo 142, 3 lecturas, 64.5s)
🔁 Placa corregida HCK948 → HCV948  (vehículo 205, 14 lecturas)

=== Placas confirmadas en moto_bogota_2.mp4: 6 ===
  OEO81E     36.0s    17 lecturas
  KAV637     44.3s    11 lecturas  🚨 ALERTA
  CTB816     64.3s    25 lecturas  🚨 ALERTA
```

| Tecla | Acción |
|---|---|
| `q` | salir |
| `espacio` | pausar / continuar |

### 2. Cargar placas de interés

Crear un CSV con las placas a vigilar:

```csv
placa,motivo
ABC123,Vehículo reportado
XYZ789,Prueba
```

Y cargarlo en la base de datos:

```powershell
python -m scripts.cargar_placas placas.csv
```

### 3. Ver las alertas

Al volver a procesar el video, cada placa de la lista que aparezca genera:

```
WARNING src.alerts: 🚨 ALERTA  ABC123  en video.mp4 (64.5s)  motivo: Vehículo reportado
```

y se dibuja con una **caja roja** en la ventana y en el video de salida (pitido opcional con
`sonido_alerta: true`). Cada vehículo alerta una sola vez.

> Para probar: procesar un video, tomar 2-3 placas que salgan en el resumen, cargarlas con
> `cargar_placas.py` y volver a procesarlo.

### 4. Correr las pruebas

```powershell
python -m pytest tests
```

---

## ⚙️ Configuración (`config.yaml`)

Todos los parámetros se ajustan aquí, sin tocar código:

```yaml
video: data/videos                # carpeta (todos sus videos) o un archivo
formato_placa: colombia          # generico | colombia
procesar_cada_n_frames: 2        # analiza 1 de cada N frames
confianza_minima_deteccion: 0.4  # umbral de YOLO (0 a 1)
alto_minimo_caja_px: 15          # ignora placas demasiado pequeñas
margen_recorte: 0.1              # margen extra al recortar la placa
alto_recorte_ocr_px: 100         # altura del recorte antes del OCR
proporcion_alto_linea_ocr: 0.6   # ignora textos pequeños (municipio)
ocr_usar_gpu: false
votos_minimos_para_confirmar: 3  # lecturas del mismo vehículo antes de confirmar su placa
tracker: bytetrack.yaml          # seguimiento de YOLO
segundos_fusion_vehiculos: 10    # placa casi igual que reaparece antes = mismo vehículo
sonido_alerta: false
mostrar_ventana: true
guardar_video_salida: true
ruta_bd: data/placas.db
ruta_log: outputs/lecturas.csv
modelo_detector: models/detector_colombia.pt   # otros países: models/detector_placas.pt
```

### Formatos de placa

| Modo | Regla | Corrección por posición |
|---|---|---|
| `colombia` | carro `^[A-Z]{3}[0-9]{3}$` (ej. `ABC123`) · moto `^[A-Z]{3}[0-9]{2}[A-Z]$` (ej. `ABC12D`) | ✅ letras: `0→O 1→I 5→S 8→B 2→Z 6→G 4→A` · números: `O/D/Q→0 I/L→1 S→5 B→8 Z→2 G→6 A→4` |
| `generico` | 5 a 8 caracteres alfanuméricos | ❌ |

---

## 📤 Salidas

| Archivo | Contenido |
|---|---|
| `outputs/lecturas.csv` | todas las lecturas válidas: video, frame, segundo, vehículo (track_id), texto leído, confianza OCR, placa confirmada, coincidencia (0/1) |
| `outputs/<video>_procesado.mp4` | video con las placas enmarcadas (verde = confirmada, rojo = alerta, amarillo = sin confirmar) |
| `data/placas.db` | base SQLite con las placas de interés y el historial (una fila por vehículo) |

### Esquema de la base de datos

```sql
CREATE TABLE placas_interes (
    placa       TEXT PRIMARY KEY,   -- normalizada, ej. ABC123
    motivo      TEXT,
    creado_en   TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE detecciones (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    video        TEXT,
    frame        INTEGER,
    segundo      REAL,
    placa        TEXT,
    confianza    REAL,
    coincidencia INTEGER            -- 0/1
);
```

---

## 🗂️ Estructura del proyecto

```
lector_placas/
├── config.yaml              # parámetros ajustables
├── requirements.txt
├── src/
│   ├── main.py              # punto de entrada
│   ├── config.py            # carga de config.yaml
│   ├── video_source.py      # fuente de video (archivo hoy, cámara mañana)
│   ├── detector.py          # detección de placas con YOLO
│   ├── ocr.py               # recorte, preprocesado y OCR
│   ├── plate_utils.py       # normalización y validación del texto
│   ├── tracker.py           # votación temporal de lecturas
│   ├── database.py          # acceso a SQLite
│   └── alerts.py            # notificación de coincidencias
├── scripts/
│   ├── descargar_modelo.py  # baja el detector YOLO desde Hugging Face
│   └── cargar_placas.py     # carga placas de interés desde CSV
├── tests/                   # pruebas: plate_utils, ocr, tracker, database
├── docs/
│   └── EXPLICACION.md       # explicación detallada del código, con diagramas
├── data/                    # videos y BD (no se suben a git)
├── models/                  # pesos de los modelos (no se suben a git)
└── outputs/                 # resultados (no se suben a git)
```

---

## 🧠 Modelos utilizados

| Modelo | Uso | Tamaño | Origen |
|---|---|---|---|
| YOLOv8n – placas Colombia | detección de placas colombianas (carros y motos) | 6,2 MB | [Rotsen2/detector-placas-colombia](https://huggingface.co/Rotsen2/detector-placas-colombia) |
| YOLOv11n – license plates | detección de placas de otros países | 5,2 MB | [morsetechlab/yolov11-license-plate-detection](https://huggingface.co/morsetechlab/yolov11-license-plate-detection) |
| CRAFT | localización de texto (EasyOCR) | 79 MB | [EasyOCR](https://github.com/JaidedAI/EasyOCR) |
| english_g2 | reconocimiento de caracteres (EasyOCR) | 14 MB | [EasyOCR](https://github.com/JaidedAI/EasyOCR) |

---

## ⚠️ Limitaciones conocidas

- Desenfoque por movimiento y vibración del casco.
- Placas lejanas, muy inclinadas, sucias o tapadas.
- Condiciones de luz difíciles: noche, contraluz, reflejos.
- En modo `generico` no hay corrección por posición, por lo que confusiones como `1↔I` o `M↔H` son más frecuentes.

---

## 🛣️ Hoja de ruta

- [x] **Fase 1** – Prototipo offline con video grabado.
- [ ] **Fase 2** – Fuente en vivo (webcam, cámara IP, cámara de acción por RTSP).
- [ ] **Fase 3** – Ejecución en dispositivo embebido (Raspberry Pi 5 / Jetson / celular) y alerta al motociclista (sonido en el casco, vibración, app).
- [ ] **Fase 4** – Base de datos central sincronizada y registro con GPS.

---

## 🔒 Privacidad y aspectos legales

Las placas y su ubicación son **datos personales** según la Ley 1581 de 2012 (Habeas Data, Colombia). Este proyecto guarda solo lo necesario; la base de datos debe protegerse y su acceso limitarse a personas autorizadas y con un propósito definido.

Los videos de prueba descargados de internet se usan únicamente para desarrollo local, respetando su licencia (p. ej. [Pexels](https://www.pexels.com/license/)).

---

## 📝 Licencia

El modelo detector y la librería Ultralytics se distribuyen bajo **AGPL-3.0**; cualquier distribución de este proyecto debe respetar esa licencia.
