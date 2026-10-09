# 🏍️ Lector de placas desde casco de moto

Sistema de reconocimiento automático de placas vehiculares (ALPR) pensado para una cámara montada en el casco de un motociclista. Lee las placas de los carros **desde atrás**, las compara contra una base de datos de placas de interés y genera una **alerta** cuando hay coincidencia.

> **Fase 1 – prototipo offline:** procesa videos ya grabados (`.mp4`) en un PC. Todo corre en local, sin servicios en la nube.

---

## ✨ Características

- 🎯 **Detección de placas** con YOLOv11 nano (liviano, pensado para dispositivos pequeños).
- 🔤 **Lectura de caracteres (OCR)** con EasyOCR, con preprocesado (escala de grises, escalado y CLAHE).
- 🇨🇴 **Validación de formato colombiano** (`ABC123`) con corrección automática de confusiones típicas del OCR según la posición (`8→B`, `O→0`, …), o modo **genérico** para placas de otros países.
- 🗳️ **Votación temporal**: una placa se confirma solo cuando se lee igual en varios frames, lo que reduce los falsos positivos.
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
5. **Votación temporal**: agrupa las lecturas de la misma placa en frames seguidos y confirma la más votada.
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

# Descargar el modelo detector de placas (≈5 MB)
python -m scripts.descargar_modelo
```

> Los modelos de EasyOCR (≈95 MB) se descargan automáticamente la primera vez que se ejecuta el programa.

---

## ▶️ Uso

### 1. Procesar un video

```powershell
python -m src.main --video data/videos/prueba_1.mp4
```

Si no se pasa `--video`, se usa el definido en `config.yaml`.

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
🚨 ALERTA  frame 102 (3.4s): ABC123 – Vehículo reportado
```

y se dibuja con una **caja roja** en la ventana y en el video de salida.

### 4. Correr las pruebas

```powershell
python -m pytest tests
```

---

## ⚙️ Configuración (`config.yaml`)

Todos los parámetros se ajustan aquí, sin tocar código:

```yaml
video: data/videos/prueba_1.mp4
formato_placa: generico          # generico | colombia
procesar_cada_n_frames: 2        # analiza 1 de cada N frames
confianza_minima_deteccion: 0.4  # umbral de YOLO (0 a 1)
alto_minimo_caja_px: 15          # ignora placas demasiado pequeñas
margen_recorte: 0.1              # margen extra al recortar la placa
alto_recorte_ocr_px: 100         # altura del recorte antes del OCR
ocr_usar_gpu: false
votos_minimos_para_confirmar: 3  # lecturas iguales necesarias para confirmar
mostrar_ventana: true
guardar_video_salida: true
ruta_bd: data/placas.db
ruta_log: outputs/lecturas.csv
modelo_detector: models/detector_placas.pt
```

### Formatos de placa

| Modo | Regla | Corrección por posición |
|---|---|---|
| `colombia` | `^[A-Z]{3}[0-9]{3}$` (ej. `ABC123`) | ✅ letras: `0→O 1→I 5→S 8→B 2→Z 6→G 4→A` · números: `O/D/Q→0 I/L→1 S→5 B→8 Z→2 G→6 A→4` |
| `generico` | 5 a 8 caracteres alfanuméricos | ❌ |

---

## 📤 Salidas

| Archivo | Contenido |
|---|---|
| `outputs/lecturas.csv` | segundo del video, número de frame, placa, confianza, coincidencia (0/1) |
| `outputs/video_procesado.mp4` | video con las placas enmarcadas y su texto (rojo = alerta) |
| `data/placas.db` | base SQLite con las placas de interés y el historial de detecciones |

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
├── tests/
│   └── test_plate_utils.py
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
| YOLOv11n – license plates | detección de placas | 5,2 MB | [morsetechlab/yolov11-license-plate-detection](https://huggingface.co/morsetechlab/yolov11-license-plate-detection) |
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
