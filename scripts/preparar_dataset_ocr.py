"""Arma el dataset del OCR: recortes de placa + su texto, a partir del dataset de caracteres.

Entrada: data/datasets/caracteres (Roboflow helian/placa_colombia, formato YOLO), donde
cada imagen trae la caja de la placa (clase 'placa') y la de cada carácter (0-9, A-Z).
Salida:  data/datasets/ocr/<split>/*.jpg y data/datasets/ocr/<split>.csv
         (columnas image_path, plate_text: el formato que pide fast-plate-ocr).

El texto se arma con los caracteres cuyo centro cae dentro de la placa, ordenados por
filas (las placas de moto tienen dos: ABC / 12D) y de izquierda a derecha. Solo se
guardan placas que cumplen el formato colombiano (carro ABC123 o moto ABC12D).

Uso:
    python -m scripts.preparar_dataset_ocr
"""
import argparse
import csv
import logging
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
import yaml

from src.plate_utils import REGEX_CARRO, REGEX_MOTO, validar_colombia

logger = logging.getLogger(__name__)

CLASE_PLACA = "placa"
SPLITS = ("train", "valid", "test")

Caja = tuple[float, float, float, float]  # x1, y1, x2, y2 normalizados (0-1)


def leer_etiquetas(ruta: Path, nombres: list[str]) -> list[tuple[str, Caja]]:
    """Lee un .txt YOLO; acepta cajas (cx cy w h) y polígonos (x1 y1 x2 y2 ...)."""
    etiquetas = []
    for linea in ruta.read_text().splitlines():
        valores = linea.split()
        if len(valores) < 5:
            continue
        clase, nums = nombres[int(valores[0])], np.array(valores[1:], dtype=float)
        if len(nums) == 4:
            cx, cy, w, h = nums
            caja = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
        else:
            puntos = nums[: len(nums) // 2 * 2].reshape(-1, 2)
            (x1, y1), (x2, y2) = puntos.min(0), puntos.max(0)
            caja = (x1, y1, x2, y2)
        etiquetas.append((clase, tuple(float(v) for v in caja)))
    return etiquetas


def texto_de_placa(placa: Caja, caracteres: list[tuple[str, Caja]]) -> str:
    """Une los caracteres dentro de la placa por filas (arriba→abajo) y luego por x."""
    px1, py1, px2, py2 = placa
    dentro = []
    for c, (x1, y1, x2, y2) in caracteres:
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        if px1 <= cx <= px2 and py1 <= cy <= py2:
            dentro.append((c, cx, cy, y2 - y1))
    if not dentro:
        return ""
    alto_medio = float(np.median([d[3] for d in dentro]))
    dentro.sort(key=lambda d: d[2])
    filas, fila = [], [dentro[0]]
    for d in dentro[1:]:
        # Un salto vertical de más de medio carácter = fila nueva
        if d[2] - fila[-1][2] > 0.5 * alto_medio:
            filas.append(fila)
            fila = []
        fila.append(d)
    filas.append(fila)
    return "".join(d[0] for f in filas for d in sorted(f, key=lambda d: d[1]))


def recortar(imagen: np.ndarray, caja: Caja, margen: float) -> np.ndarray:
    """Recorta la caja normalizada con un margen proporcional, sin salirse de la imagen."""
    alto, ancho = imagen.shape[:2]
    x1, y1, x2, y2 = caja
    mx, my = (x2 - x1) * margen, (y2 - y1) * margen
    x1, x2 = int(max(0, (x1 - mx) * ancho)), int(min(ancho, (x2 + mx) * ancho))
    y1, y2 = int(max(0, (y1 - my) * alto)), int(min(alto, (y2 + my) * alto))
    return imagen[y1:y2, x1:x2]


def procesar_split(origen: Path, destino: Path, split: str, nombres: list[str],
                   margen: float, alto_minimo_px: int) -> tuple[list[tuple[str, str]], Counter]:
    """Recorta las placas de un split; devuelve filas (ruta relativa, texto) y estadísticas."""
    estadisticas = Counter()
    carpeta_salida = destino / split
    carpeta_salida.mkdir(parents=True, exist_ok=True)
    filas_csv = []
    for ruta_img in sorted((origen / split / "images").glob("*.jpg")):
        etiquetas = leer_etiquetas(origen / split / "labels" / f"{ruta_img.stem}.txt", nombres)
        placas = [caja for clase, caja in etiquetas if clase == CLASE_PLACA]
        caracteres = [(c, caja) for c, caja in etiquetas if c != CLASE_PLACA]
        if not placas:
            continue
        imagen = cv2.imread(str(ruta_img))
        for i, placa in enumerate(placas):
            crudo = texto_de_placa(placa, caracteres)
            texto = validar_colombia(crudo)
            if texto is None:
                estadisticas["descartada_formato"] += 1
                logger.debug("Descartada %s: %r", ruta_img.name, crudo)
                continue
            if texto != crudo:
                estadisticas["corregida_por_posicion"] += 1
            recorte = recortar(imagen, placa, margen)
            if recorte.shape[0] < alto_minimo_px:
                estadisticas["descartada_pequena"] += 1
                continue
            nombre = f"{ruta_img.stem}_{i}.jpg"
            cv2.imwrite(str(carpeta_salida / nombre), recorte)
            filas_csv.append((f"{split}/{nombre}", texto))
            estadisticas["moto" if REGEX_MOTO.match(texto) else "carro"] += 1
    return filas_csv, estadisticas


def quitar_fuga(filas: dict[str, list[tuple[str, str]]]) -> None:
    """Pasa a train los recortes de valid/test cuya placa ya está en train.

    El mismo vehículo aparece en varias fotos; si su placa está en train y en valid,
    la validación mide memoria y no generalización.
    """
    en_train = {texto for _, texto in filas["train"]}
    for split in ("valid", "test"):
        repetidas = [f for f in filas[split] if f[1] in en_train]
        filas[split] = [f for f in filas[split] if f[1] not in en_train]
        filas["train"].extend(repetidas)
        logger.info("%s: %d recortes con placa ya vista en train → movidos a train", split, len(repetidas))
    # Lo mismo entre valid y test
    en_valid = {texto for _, texto in filas["valid"]}
    repetidas = [f for f in filas["test"] if f[1] in en_valid]
    filas["test"] = [f for f in filas["test"] if f[1] not in en_valid]
    filas["valid"].extend(repetidas)


def guardar_csv(ruta: Path, filas: list[tuple[str, str]]) -> None:
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        escritor.writerow(["image_path", "plate_text"])
        escritor.writerows(filas)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--origen", type=Path, default=Path("data/datasets/caracteres"))
    parser.add_argument("--destino", type=Path, default=Path("data/datasets/ocr"))
    parser.add_argument("--margen", type=float, default=0.1, help="Igual a margen_recorte de config.yaml")
    parser.add_argument("--alto-minimo-px", type=int, default=10)
    args = parser.parse_args()

    nombres = yaml.safe_load((args.origen / "data.yaml").read_text(encoding="utf-8"))["names"]
    filas = {}
    for split in SPLITS:
        filas[split], estadisticas = procesar_split(args.origen, args.destino, split, nombres,
                                                    args.margen, args.alto_minimo_px)
        logger.info("%s: %s", split, dict(estadisticas))
    quitar_fuga(filas)
    for split in SPLITS:
        guardar_csv(args.destino / f"{split}.csv", filas[split])
        logger.info("%s.csv: %d recortes, %d placas distintas", split, len(filas[split]),
                    len({texto for _, texto in filas[split]}))


if __name__ == "__main__":
    main()
