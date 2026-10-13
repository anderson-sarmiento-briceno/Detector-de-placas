"""Paso 1 del etiquetado del detector: encuentra todas las cajas candidatas y las lee.

Junta las cajas de dos detectores (el colombiano liviano y un "maestro" grande, más lento
pero más sensible, ambos a confianza baja) y lee cada caja con el OCR colombiano.
No decide nada: guarda todo en cajas.csv para que `scripts.generar_etiquetas` aplique
las reglas (y la revisión humana) sin volver a correr los modelos.

Salida: --carpeta/cajas.csv con una fila por caja (o una fila vacía si el frame no tiene).

Uso:
    python -m scripts.autoetiquetar --carpeta data/datasets/detector_video/entrenamiento
"""
import argparse
import csv
import logging
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

from src.config import cargar_config
from src.detector import Deteccion
from src.ocr import LectorONNX
from src.plate_utils import FORMATO_COLOMBIA, validar_placa

logger = logging.getLogger(__name__)

IOU_MISMA_CAJA = 0.4


def iou(a: Deteccion, b: Deteccion) -> float:
    ix = max(0, min(a.x2, b.x2) - max(a.x1, b.x1))
    iy = max(0, min(a.y2, b.y2) - max(a.y1, b.y1))
    inter = ix * iy
    union = (a.x2 - a.x1) * (a.y2 - a.y1) + (b.x2 - b.x1) * (b.y2 - b.y1) - inter
    return inter / union if union else 0.0


def detectar(modelo: YOLO, imagen: np.ndarray, conf: float, imgsz: int) -> list[Deteccion]:
    r = modelo.predict(imagen, conf=conf, imgsz=imgsz, verbose=False)[0]
    return [Deteccion(*map(int, c), confianza=s) for c, s in zip(r.boxes.xyxy.tolist(), r.boxes.conf.tolist())]


def unir(cajas: list[Deteccion]) -> list[Deteccion]:
    """Quita duplicados entre detectores: de cajas solapadas queda la de mayor confianza."""
    resultado: list[Deteccion] = []
    for c in sorted(cajas, key=lambda c: -c.confianza):
        if all(iou(c, r) < IOU_MISMA_CAJA for r in resultado):
            resultado.append(c)
    return resultado


COLUMNAS = ["frame", "ancho", "alto", "x1", "y1", "x2", "y2", "conf_det", "detector",
            "texto", "conf_ocr", "placa_valida"]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--carpeta", type=Path, required=True, help="Carpeta con images/")
    parser.add_argument("--maestro", default="models/maestro_placas_l.pt")
    parser.add_argument("--conf-deteccion", type=float, default=0.15)
    parser.add_argument("--imgsz-maestro", type=int, default=1280)
    args = parser.parse_args()

    config = cargar_config("config.yaml")
    detectores = [("colombia", YOLO(config["modelo_detector"]), 640),
                  ("maestro", YOLO(args.maestro), args.imgsz_maestro)]
    lector = LectorONNX(config["modelo_ocr"], config["config_modelo_ocr"], config["margen_recorte"])

    imagenes = sorted((args.carpeta / "images").glob("*.jpg"))
    with open(args.carpeta / "cajas.csv", "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUMNAS)
        escritor.writeheader()
        for i, ruta in enumerate(imagenes):
            imagen = cv2.imread(str(ruta))
            alto, ancho = imagen.shape[:2]
            candidatas = []
            for nombre, modelo, imgsz in detectores:
                for c in detectar(modelo, imagen, args.conf_deteccion, imgsz):
                    c.track_id = nombre  # se reutiliza el campo para recordar qué detector la halló
                    candidatas.append(c)
            cajas = unir(candidatas)
            if not cajas:
                escritor.writerow({"frame": ruta.name, "ancho": ancho, "alto": alto})
            for c in cajas:
                texto, conf = lector.leer(imagen, c)
                escritor.writerow({
                    "frame": ruta.name, "ancho": ancho, "alto": alto,
                    "x1": c.x1, "y1": c.y1, "x2": c.x2, "y2": c.y2,
                    "conf_det": round(c.confianza, 3), "detector": c.track_id, "texto": texto,
                    "conf_ocr": round(conf, 3),
                    "placa_valida": int(validar_placa(texto, FORMATO_COLOMBIA) is not None),
                })
            if (i + 1) % 300 == 0:
                logger.info("%d/%d frames", i + 1, len(imagenes))
    logger.info("Cajas candidatas en %s", args.carpeta / "cajas.csv")


if __name__ == "__main__":
    main()
