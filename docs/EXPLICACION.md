# Cómo funciona el lector de placas (explicación paso a paso)

> Documento para ir entendiendo el código. Se actualiza a medida que avanzamos.
> Estado: **Fase 1 completa** (video → detección + seguimiento → OCR → validación → votación → BD → alertas).

---

## 1. La idea general

Un video es solo una secuencia de fotos (frames). El programa toma cada foto y le hace
dos preguntas, cada una respondida por un modelo de inteligencia artificial distinto:

1. **¿Dónde hay una placa?** → lo responde **YOLO** (detector de objetos).
2. **¿Qué dice esa placa?** → lo responde **EasyOCR** (lector de texto).

Después, código "normal" (sin IA) limpia el texto y decide si parece una placa válida.

```
                ┌──────────────────────────── por cada frame ────────────────────────────┐
                │                                                                        │
 prueba_1.mp4 ──┼─► FuenteArchivo ──► DetectorPlacas ──► LectorOCR ──► validar_placa ──► │ ──► consola + ventana
  (642 frames)  │   video_source.py   detector.py        ocr.py        plate_utils.py    │     + video_procesado.mp4
                │   "dame un frame"   "¿dónde hay        "¿qué dice    "¿es una placa    │     + resumen final
                │                      placas?"          la placa?"    válida?"          │
                └────────────────────────────────────────────────────────────────────────┘
                                         ▲                     ▲
                                  models/detector_       ~/.EasyOCR/model/
                                  placas.pt (YOLO)       (CRAFT + english_g2)
```

`main.py` es el "director de orquesta": no hace el trabajo pesado, solo llama a cada pieza en orden.

---

## 2. Los archivos y qué hace cada uno

```
lector_placas/
├── config.yaml              ← TODOS los parámetros ajustables (umbrales, rutas…)
├── requirements.txt         ← librerías a instalar
├── src/
│   ├── main.py              ← punto de entrada; une todas las piezas
│   ├── config.py            ← lee config.yaml
│   ├── video_source.py      ← entrega frames del video
│   ├── detector.py          ← YOLO: encuentra placas (cajas)
│   ├── ocr.py               ← recorta, mejora la imagen y lee el texto
│   ├── plate_utils.py       ← limpia y valida el texto (genérico / Colombia)
│   ├── tracker.py           ← votación: junta lecturas del mismo vehículo → 1 placa
│   ├── database.py          ← SQLite: placas de interés + historial
│   └── alerts.py            ← aviso cuando una placa está en la lista
├── scripts/
│   ├── descargar_modelo.py  ← baja los modelos YOLO desde Hugging Face
│   └── cargar_placas.py     ← carga placas de interés desde un CSV
├── tests/                   ← pruebas automáticas (42)
├── models/                  ← detector_colombia.pt, detector_placas.pt
├── data/videos/             ← los videos a procesar (todos los de la carpeta)
├── data/placas.db           ← la base de datos
└── outputs/                 ← <video>_procesado.mp4 + lecturas.csv
```

¿Por qué separado en tantos archivos? Para poder **cambiar una pieza sin tocar las demás**:
mañana cambiamos el video por una cámara (solo se toca `video_source.py`), o EasyOCR por
otro OCR (solo `ocr.py`), o el formato de placa (solo `plate_utils.py`).

---

## 3. Recorrido de un frame, pieza por pieza

### 3.1 `config.py` + `config.yaml` — la configuración

`config.yaml` es un archivo de texto con pares `clave: valor`. `cargar_config()` lo convierte
en un diccionario de Python. Así, para cambiar un umbral **no se toca código**:

| Clave | Valor | Qué controla |
|---|---|---|
| `video` | `data/videos/prueba_1.mp4` | qué video procesar |
| `formato_placa` | `generico` | reglas de validación (`generico` o `colombia`) |
| `procesar_cada_n_frames` | `2` | analiza 1 de cada 2 frames (el doble de rápido) |
| `confianza_minima_deteccion` | `0.4` | YOLO debe estar ≥ 40 % seguro de que es placa |
| `alto_minimo_caja_px` | `15` | placas de menos de 15 px de alto se ignoran (ilegibles) |
| `margen_recorte` | `0.1` | al recortar la placa se agrega 10 % de borde |
| `alto_recorte_ocr_px` | `100` | el recorte se agranda a 100 px de alto antes del OCR |
| `mostrar_ventana` | `true` | mostrar el video en pantalla |
| `guardar_video_salida` | `true` | guardar `outputs/video_procesado.mp4` |

### 3.2 `video_source.py` — de dónde salen las imágenes

```
 archivo mp4 ──► cv2.VideoCapture ──► grab() ──► ¿numero % cada_n == 0? ──sí──► retrieve() ──► Frame
                                        ▲                │                                   (imagen,
                                        │                no                                   numero,
                                        └────────────────┘ (se salta sin decodificar)         segundo)
```

- `cv2.VideoCapture` (OpenCV) abre el video.
- `grab()` avanza al siguiente frame **sin decodificarlo** (rápido); `retrieve()` sí lo
  decodifica a una imagen. Por eso saltar frames ahorra tiempo de verdad.
- Cada frame sale como un objeto `Frame` con: la **imagen** (una matriz de números
  1080 × 1920 × 3 colores BGR), su **número** y su **segundo** en el video.
- La clase se usa con `for frame in fuente:` — es un *iterador*: entrega un frame a la vez,
  sin cargar el video entero en memoria.

### 3.3 `detector.py` — YOLO encuentra las placas

```
  imagen completa (1920×1080)                    lista de Deteccion
 ┌──────────────────────────────┐               ┌────────────────────────────────────┐
 │        🚗          🛵         │   YOLO        │ x1=1676 y1=660 x2=1912 y2=800 c=0.81│
 │      [▭▭]        [▭]   🚙     │ ──────────►  │ x1=154  y1=598 x2=223  y2=644 c=0.66│
 │                       [▭▭▭]  │  predict()    │ x1=474  y1=460 x2=543  y2=493 c=0.61│
 └──────────────────────────────┘               └────────────────────────────────────┘
```

- `YOLO("models/detector_placas.pt")` carga la red neuronal.
- `modelo.predict(imagen, conf=0.4)` devuelve las **cajas** (rectángulos) donde cree que hay
  placas, cada una con su **confianza** (0 a 1).
- Cada caja se guarda en un `Deteccion(x1, y1, x2, y2, confianza)`:
  `(x1, y1)` = esquina superior izquierda, `(x2, y2)` = esquina inferior derecha, en píxeles.
- Se descartan cajas con alto < `alto_minimo_caja_px`.

YOLO **no lee** la placa: solo dice "aquí hay un rectángulo que parece una placa".

### 3.4 `ocr.py` — recortar, mejorar y leer

```
 imagen ──► recortar() ──► preprocesar() ──────────────────────────────► EasyOCR ──► "AJE-1610", 0.86
            caja + 10%     ├ escala de grises (1 canal en vez de 3)
                           ├ agrandar a 100 px de alto (INTER_CUBIC)
                           └ CLAHE: sube el contraste por zonas
```

1. **`recortar()`**: corta solo el rectángulo de la placa, con un 10 % extra de margen
   (por si YOLO cortó justo en el borde de una letra). Usa `max/min` para no salirse de la imagen.
2. **`preprocesar()`**:
   - *Escala de grises*: el color no ayuda a leer letras; quitarlo simplifica.
   - *Agrandar*: las placas lejanas miden ~30 px; el OCR lee mejor letras grandes.
   - *CLAHE* (ecualización adaptativa de histograma): mejora el contraste por partes, útil
     con sombras o reflejos parciales.
3. **`LectorOCR.leer()`**: EasyOCR puede encontrar **varios** textos dentro del recorte
   (p. ej. la placa + el nombre del municipio debajo). Nos quedamos con el de **letras más
   grandes** (la caja de texto más alta), que es la línea principal de la placa.
   Además le decimos que solo considere `A-Z`, `0-9` y `-` (`allowlist`).

### 3.5 `plate_utils.py` — ¿esto es una placa?

```
 texto crudo ──► normalizar() ──► ¿formato? ──generico──► ¿5 a 8 alfanuméricos? ──sí──► "AJE1610"
 "aje-1610"      "AJE1610"           │                                           └no──► None (descartada)
                                     └──colombia──► corregir_colombia() ──► ¿ABC123? ──sí──► placa
                                                    (0→O en letras,                  └no──► None
                                                     O→0 en números…)
```

- `normalizar()`: mayúsculas y quita todo lo que no sea letra o número (`"abc-123"` → `"ABC123"`).
- **Modo `generico`** (el actual, porque el video es de Taiwán): acepta 5 a 8 caracteres.
- **Modo `colombia`**: como sabemos que es `LLLNNN`, si el OCR leyó `8` donde va una letra,
  lo cambiamos a `B`; si leyó `O` donde va un número, a `0`. Luego exige `^[A-Z]{3}[0-9]{3}$`.
- Esta pieza **no usa IA**: son reglas, por eso tiene tests automáticos (20 pruebas).

### 3.6 `main.py` — el director

```
 cargar config ─► buscar videos en data/videos ─► cargar YOLO + EasyOCR + BD ─► por cada video:
                                                                                     │
              ┌──────────────────────────────────────────────────────────────────────┘
              ▼
   ┌──► siguiente frame ──(no hay más)──► guardar en BD 1 fila por vehículo ─► imprimir resumen
   │          │
   │          ▼
   │    detectar + seguir placas (cada caja trae un track_id = "vehículo n.º 142")
   │          │
   │          ▼
   │    por cada caja: OCR ──► validar ──► votación del vehículo ──► ¿placa nueva o cambió?
   │                                                                   └ sí → ¿está en la BD? → 🚨 alerta
   │          │                                                          + fila en lecturas.csv
   │          ▼
   │    dibujar: VERDE = confirmada · ROJO = alerta · AMARILLO = aún sin confirmar
   │    escribir frame al video de salida, mostrar ventana
   │          │
   └──────────┴── (tecla q = salir, espacio = pausa)
```

- Los modelos se cargan **una sola vez** al inicio (cargar es lento; usar es rápido).
- La clase `Pipeline` guarda las piezas (detector, OCR, BD) y `procesar_video()` recorre un video.

### 3.7 `tracker.py` — votación: de 30 lecturas imperfectas a 1 placa

**Paso A — seguimiento (en `detector.py`).** YOLO no solo detecta: con `model.track()` y el
algoritmo **ByteTrack** le pone a cada caja un número (`track_id`) que se mantiene mientras el
vehículo sigue en pantalla. Así sabemos que las lecturas de los frames 846, 858, 864… son del
**mismo** vehículo.

**Paso B — votación por carácter.** El OCR rara vez lee igual la placa entera, pero cada
posición sí suele acertar la mayoría de las veces:

```
 Lecturas del vehículo 103 (moto):
     I E O 8 1 E
     D E O 8 1 E
     O E O 8 1 E
     D E O 8 1 E
     N E O 8 1 E
     D Z O 8 1 E
     ─────────────
 voto: D E O 8 1 E   ← en cada columna gana la letra más repetida
```

- Antes de votar se agrupan las lecturas por **patrón** (`LLLNNN` carro / `LLLNNL` moto) y se usa
  el patrón más común, para no mezclar columnas.
- Empates → gana el carácter con más confianza del OCR sumada.
- Se confirma cuando el vehículo tiene `votos_minimos_para_confirmar` (3) lecturas válidas.
- Si con más lecturas el voto cambia, la placa se **corrige** (en consola sale `🔁 corregida`).

**Paso C — fusión.** A veces el seguimiento pierde el vehículo (lo tapa otro, sale del cuadro)
y al volver le da un ID nuevo. Si el nuevo confirma una placa que difiere en **máximo 1 carácter**
de un vehículo visto hace menos de `segundos_fusion_vehiculos` (10 s), se unen:

```
 vehículo 103: DEO81E (36,0–36,3 s) ┐
 vehículo 106: IEO81E (39,6–41,1 s) ├─► un solo vehículo, 17 lecturas → OEO81E
 vehículo 117: TEO81E (46,4–47,2 s) ┘
```

### 3.8 `database.py`, `alerts.py` y `scripts/cargar_placas.py`

- **BD SQLite** (`data/placas.db`, un solo archivo, no necesita servidor):
  - `placas_interes`: la lista de placas a vigilar (`placa`, `motivo`).
  - `detecciones`: historial — **una fila por vehículo** con su placa final.
- `cargar_placas.py` lee un CSV `placa,motivo`, normaliza (`abc-123` → `ABC123`) y lo guarda.
- Cada vez que un vehículo confirma (o corrige) su placa, se busca en `placas_interes` por
  **igualdad exacta**. Si está → `alertar()`: mensaje `🚨 ALERTA` en consola, caja **roja** y
  pitido opcional (`sonido_alerta: true`). Cada vehículo alerta una sola vez.
- `outputs/lecturas.csv`: **todas** las lecturas válidas (frame, segundo, vehículo, texto leído,
  placa confirmada en ese momento, si coincide). Sirve para revisar qué pasó.

---

## 4. Los modelos: qué son, dónde están y cuánto pesan

Hay **3 redes neuronales** en total, todas ya entrenadas por otros (nosotros solo las usamos):

| Modelo | Para qué | Dónde está en tu PC | Peso |
|---|---|---|---|
| **YOLOv11 nano** (placas) | encontrar placas en el frame | `lector_placas\models\detector_placas.pt` | **5,2 MB** |
| **CRAFT** (de EasyOCR) | encontrar *zonas de texto* dentro del recorte | `C:\Users\Usuario\.EasyOCR\model\craft_mlt_25k.pth` | **79,3 MB** |
| **english_g2** (de EasyOCR) | reconocer *qué letras* hay en esa zona | `C:\Users\Usuario\.EasyOCR\model\english_g2.pth` | **14,4 MB** |

Otros pesos en disco relacionados:

| Qué | Dónde | Peso |
|---|---|---|
| Copia en caché del YOLO (de la descarga) | `C:\Users\Usuario\.cache\huggingface\hub\…` | 5,2 MB (se puede borrar) |
| Entorno virtual completo (todas las librerías) | `lector_placas\.venv` | ~1,25 GB |
| …de eso, solo PyTorch | `.venv\Lib\site-packages\torch` | ~500 MB |
| Video de prueba | `data\videos\prueba_1.mp4` | 15,2 MB |
| Video procesado | `outputs\video_procesado.mp4` | 55,8 MB |

**De dónde salieron:**
- El YOLO lo bajó `scripts/descargar_modelo.py` desde Hugging Face
  ([morsetechlab/yolov11-license-plate-detection](https://huggingface.co/morsetechlab/yolov11-license-plate-detection)).
  Es un YOLOv11 "nano" (el más liviano, ~2,6 millones de parámetros) re-entrenado con miles
  de fotos de placas de varios países. Licencia AGPL-3.0.
- Los de EasyOCR se descargaron **solos** la primera vez que corrió el programa.

**¿Qué es un archivo `.pt` / `.pth`?** Son los "pesos" de la red: millones de números que
la red aprendió durante su entrenamiento. El código de la red (la arquitectura) está en las
librerías (`ultralytics`, `easyocr`); el archivo solo trae los números aprendidos.

**¿Por qué PyTorch pesa tanto?** Es el motor matemático que ejecutan las tres redes.
Tu instalación es la versión **solo CPU** (no se detectó tarjeta NVIDIA), por eso corre a ~11 FPS.

---

## 5. Cómo se construyó (orden y decisiones)

| Paso | Qué se hizo | Por qué así |
|---|---|---|
| 1 | Carpetas, `.venv`, `requirements.txt`, `config.yaml`, `.gitignore` | entorno aislado; nada "quemado" en el código; no subir videos/modelos/BD a git |
| 2 | `video_source.py` + `main.py` solo mostrando video | probar lo más simple primero; la fuente queda intercambiable (cámara en Fase 2) |
| — | Quitar `opencv-python-headless` | EasyOCR lo instaló y choca con `opencv-python` (rompía la ventana) |
| 3 | `detector.py` + descarga del YOLO | modelo nano = liviano, pensado para correr luego en un dispositivo pequeño |
| 4 | `ocr.py` + `plate_utils.py` + tests | EasyOCR es el más simple para arrancar; la validación tiene tests porque son reglas exactas |
| — | Ajuste a Colombia (sección 6.1) | detector colombiano, motos, OCR multilínea |
| — | Carpeta de videos | `video: data/videos` procesa todos los videos sin importar el nombre |
| 5 | `tracker.py`, `database.py`, `alerts.py`, `cargar_placas.py` | seguimiento + voto por carácter (el voto por texto exacto no sirve: el OCR casi nunca repite la placa entera) |

---

## 6. Resultados

**Antes de la votación** (video de Taiwán): cada placa se imprimía en cada frame
(≈ 65 textos distintos para ~6 placas reales):

```
 Placa real: AJE·1610
 Lecturas:   AJEI610 ×24   AJEL610 ×8   AJE1610 ×8   AJEI61C ×3   MAJEI610 ×2 …
```

**Con la votación** (video `moto_bogota_2.mp4`, 2:08, con `CTB816` y `KAV637` cargadas en una BD
de prueba):

| | Sin votación | Con votación |
|---|---|---|
| Resultado | 64 textos distintos | **6 vehículos confirmados** |
| Moto `?EO81E` | 15 variantes | 1 vehículo, 17 lecturas |
| Alertas | — | 🚨 `KAV637`, 🚨 `CTB816` |

Lo que sigue limitando: la calidad del video (grabación de pantalla comprimida). Placas como
`HCV948` siguen dudosas en 1 letra (`H/R`, `V/Y/K`) porque el OCR reparte los votos casi parejo.

---

## 6.1 Ajuste a Bogotá (video `moto_bogota.mp4`)

Qué cambió y **por qué no es "aprenderse" el video** (todo son reglas generales de Colombia):

| Cambio | Archivo | Motivo |
|---|---|---|
| Modo `colombia` acepta **carro `ABC123` y moto `ABC12D`** | `plate_utils.py` | las motos colombianas tienen otro formato |
| Corrección por plantilla (`LLLNNN` / `LLLNNL`) | `plate_utils.py` | misma idea `8→B`, `O→0`, pero según carro o moto |
| OCR une **todas las líneas grandes** y descarta las pequeñas | `ocr.py` | placas en 2 líneas o partidas; ignora "BOGOTÁ D.C." |
| Detector **colombiano** (YOLOv8n, Rotsen2) | `config.yaml` | el genérico ponía la caja sobre la luz trasera de las motos |

```
 Moto WRG-22H, segundo 85:
   detector genérico  → caja sobre la LUZ TRASERA (0.41)   → OCR no lee nada
   detector colombia  → caja sobre la PLACA       (0.77)   → OCR "VR6-22H" → corrección moto → VRG22H
```

Comparación de detectores en el video de Bogotá (974 frames):

| | genérico | colombia |
|---|---|---|
| frames con placa | 432 | 483 |
| velocidad | 32 ms/frame | 26 ms/frame |

Limitación: el video es una grabación de pantalla comprimida; muchas placas tienen pocos
píxeles y el OCR confunde letras (`W→V`, `D→O`). La votación (paso 5) y un video de mejor
calidad ayudarán.

---

## 7. Comandos

```powershell
.venv\Scripts\python -m src.main                         # procesar todos los videos de data/videos
.venv\Scripts\python -m src.main --video ruta\video.mp4  # un solo video
.venv\Scripts\python -m scripts.cargar_placas placas.csv # cargar placas de interés (CSV: placa,motivo)
.venv\Scripts\python -m pytest tests                     # pruebas
.venv\Scripts\python -m scripts.descargar_modelo --modelo colombia   # re-descargar detector
```

## 8. Glosario rápido

- **Frame**: una imagen del video (este video tiene 30 por segundo).
- **Bounding box / caja**: rectángulo `(x1, y1, x2, y2)` que rodea un objeto.
- **Confianza**: qué tan seguro está el modelo (0 = nada, 1 = total).
- **YOLO**: "You Only Look Once", familia de detectores de objetos rápidos.
- **OCR**: reconocimiento óptico de caracteres (imagen → texto).
- **CLAHE**: técnica para mejorar el contraste por zonas de la imagen.
- **Regex**: patrón de texto, p. ej. `^[A-Z]{3}[0-9]{3}$` = 3 letras y 3 números.
- **FPS**: frames por segundo que el programa logra procesar.
- **Votación temporal**: decidir el texto de una placa juntando las lecturas de varios frames.
- **Tracking / seguimiento**: reconocer que una caja en el frame 10 y otra en el frame 12 son el mismo objeto.
- **ByteTrack**: el algoritmo de seguimiento que usa YOLO por defecto.
- **track_id**: número que el seguimiento le asigna a cada vehículo.
- **SQLite**: base de datos en un solo archivo, incluida en Python.
