"""Reglas para decidir qué cajas candidatas son placas, y generación del dataset YOLO.

Paso 2 del etiquetado del detector (el paso 1 es scripts.autoetiquetar → cajas.csv).
Cada caja candidata termina en una de estas clases:
- placa:      el OCR la lee como placa colombiana válida con confianza ≥ CONF_OCR_PLACA,
              o una persona la marcó como placa.
- no_placa:   el OCR casi no ve caracteres (confianza < CONF_OCR_NO_PLACA) y el detector
              también duda, o una persona la marcó como no placa.
- ignorar:    demasiado pequeña para leerse, o una persona no supo decidir. Se tapa con
              gris en la imagen de entrenamiento: el detector no aprende ni que es placa
              ni que no lo es.
- revisar:    ninguna regla alcanza; se decide con scripts.revisar_cajas.

Uso:
    python -m scripts.etiquetas_detector --carpeta data/datasets/detector_video/entrenamiento
    → imprime cuántas cajas hay de cada clase y genera dataset/ (images + labels YOLO)
      con los frames que no tienen cajas pendientes de revisar.
"""
import argparse
import csv
import logging
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import cv2

logger = logging.getLogger(__name__)

CONF_OCR_PLACA = 0.5        # igual que confianza_minima_ocr del pipeline
CONF_OCR_NO_PLACA = 0.2
CONF_DET_NO_PLACA = 0.35
ALTO_MINIMO_PX = 12         # más bajas no se pueden leer (el pipeline usa 15)
GRIS = (114, 114, 114)      # color de relleno de YOLO

PLACA, NO_PLACA, IGNORAR, REVISAR = "placa", "no_placa", "ignorar", "revisar"
DECISIONES_TECLA = {"p": PLACA, "n": NO_PLACA, "i": IGNORAR}


def clave(fila: dict) -> str:
    """Identificador único de una caja: frame + coordenadas."""
    return f"{fila['frame']}|{fila['x1']},{fila['y1']},{fila['x2']},{fila['y2']}"


def clasificar(fila: dict) -> str:
    """Clase de una caja según las reglas automáticas (sin revisión humana)."""
    if int(fila["y2"]) - int(fila["y1"]) < ALTO_MINIMO_PX:
        return IGNORAR
    conf_ocr, conf_det = float(fila["conf_ocr"]), float(fila["conf_det"])
    if int(fila["placa_valida"]) and conf_ocr >= CONF_OCR_PLACA:
        return PLACA
    if conf_ocr < CONF_OCR_NO_PLACA and conf_det < CONF_DET_NO_PLACA:
        return NO_PLACA
    return REVISAR


def leer_cajas(carpeta: Path) -> list[dict]:
    with open(carpeta / "cajas.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def leer_decisiones(carpeta: Path) -> dict[str, str]:
    ruta = carpeta / "decisiones.csv"
    if not ruta.exists():
        return {}
    with open(ruta, encoding="utf-8") as f:
        return {r["caja"]: r["decision"] for r in csv.DictReader(f)}


def clase_final(fila: dict, decisiones: dict[str, str]) -> str:
    """La decisión humana manda sobre la regla automática."""
    return decisiones.get(clave(fila)) or clasificar(fila)


def generar_dataset(carpeta: Path, cajas: list[dict], decisiones: dict[str, str]) -> Counter:
    """Escribe carpeta/dataset/{images,labels} con los frames sin cajas pendientes."""
    por_frame: dict[str, list[dict]] = defaultdict(list)
    for fila in cajas:
        por_frame[fila["frame"]].append(fila)
    destino = carpeta / "dataset"
    if destino.exists():
        shutil.rmtree(destino)
    (destino / "images").mkdir(parents=True)
    (destino / "labels").mkdir()
    conteo = Counter()
    for frame, filas in por_frame.items():
        filas = [f for f in filas if f["x1"]]  # fila vacía = frame sin cajas
        clases = [clase_final(f, decisiones) for f in filas]
        if REVISAR in clases:
            conteo["frames_pendientes"] += 1
            continue
        ancho, alto = int(filas[0]["ancho"]) if filas else 0, int(filas[0]["alto"]) if filas else 0
        lineas = []
        ignorar = []
        for f, c in zip(filas, clases):
            x1, y1, x2, y2 = (int(f[k]) for k in ("x1", "y1", "x2", "y2"))
            if c == PLACA:
                lineas.append(f"0 {(x1 + x2) / 2 / ancho:.6f} {(y1 + y2) / 2 / alto:.6f} "
                              f"{(x2 - x1) / ancho:.6f} {(y2 - y1) / alto:.6f}")
            elif c == IGNORAR:
                ignorar.append((x1, y1, x2, y2))
        origen = carpeta / "images" / frame
        if ignorar:
            imagen = cv2.imread(str(origen))
            for x1, y1, x2, y2 in ignorar:
                cv2.rectangle(imagen, (x1, y1), (x2, y2), GRIS, -1)
            cv2.imwrite(str(destino / "images" / frame), imagen, [cv2.IMWRITE_JPEG_QUALITY, 95])
        else:
            shutil.copy(origen, destino / "images" / frame)
        (destino / "labels" / f"{Path(frame).stem}.txt").write_text("\n".join(lineas))
        conteo["frames_en_dataset"] += 1
        conteo["frames_negativos"] += not lineas
        conteo["placas"] += len(lineas)
    return conteo


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--carpeta", type=Path, required=True)
    args = parser.parse_args()

    cajas = leer_cajas(args.carpeta)
    decisiones = leer_decisiones(args.carpeta)
    clases = Counter(clase_final(f, decisiones) for f in cajas if f["x1"])
    logger.info("Cajas por clase: %s (decisiones humanas: %d)", dict(clases), len(decisiones))
    logger.info("Dataset: %s", dict(generar_dataset(args.carpeta, cajas, decisiones)))


if __name__ == "__main__":
    main()
