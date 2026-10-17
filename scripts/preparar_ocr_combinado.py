"""Une el dataset OCR de Roboflow con los recortes revisados de videos, para reentrenar el OCR.

De cada video (data/datasets/ocr_video/<video>, ver scripts.recortes_ocr_video y
scripts.revisar_placas_video) se usan los vehículos marcados ok o corregida. Cada vehículo
aporta varios recortes (repartidos en el tiempo, de --alto-minimo px o más), todos con la
placa confirmada. Los vehículos se reparten entre train y val (nunca el mismo vehículo en
los dos). Las motos aportan más recortes, porque es donde el OCR falla más.

Salida (rutas relativas a data/datasets, como pide fast-plate-ocr):
    data/datasets/ocr_combinado_train.csv
    data/datasets/ocr_combinado_val.csv

Uso:
    python -m scripts.preparar_ocr_combinado
"""
import argparse
import csv
import logging
import random
from collections import defaultdict
from pathlib import Path

from src.plate_utils import REGEX_MOTO

logger = logging.getLogger(__name__)

RAIZ = Path("data/datasets")
ROBOFLOW = RAIZ / "ocr"
VIDEOS = RAIZ / "ocr_video"
DECISIONES_UTILES = {"ok", "corregida"}


def leer_csv(ruta: Path) -> list[dict]:
    with open(ruta, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def repartidos(filas: list[dict], n: int) -> list[dict]:
    """Hasta n filas repartidas a lo largo de la lista (no solo las primeras)."""
    if len(filas) <= n:
        return filas
    paso = len(filas) / n
    return [filas[int(i * paso)] for i in range(n)]


def recortes_de_video(carpeta: Path, alto_minimo: int, max_carro: int, max_moto: int,
                      fraccion_val: float) -> tuple[list, list]:
    # Azar propio por video: agregar videos nuevos no cambia el reparto de los anteriores
    azar = random.Random(0)
    vehiculos = {v["track_id"]: v for v in leer_csv(carpeta / "vehiculos.csv")
                 if v["decision"] in DECISIONES_UTILES}
    por_vehiculo = defaultdict(list)
    for r in leer_csv(carpeta / "recortes.csv"):
        if r["vehiculo"] in vehiculos and int(r["alto_px"]) >= alto_minimo:
            por_vehiculo[r["vehiculo"]].append(r)
    ids = sorted(por_vehiculo)
    azar.shuffle(ids)
    n_val = max(1, round(len(ids) * fraccion_val))
    train, val = [], []
    for k, vid in enumerate(ids):
        placa = vehiculos[vid]["placa"]
        limite = max_moto if REGEX_MOTO.match(placa) else max_carro
        destino = val if k < n_val else train
        for r in repartidos(sorted(por_vehiculo[vid], key=lambda r: float(r["segundo"])), limite):
            destino.append((f"ocr_video/{carpeta.name}/recortes/{r['recorte']}", placa))
    logger.info("%s: %d vehículos (%d val), %d recortes train, %d val",
                carpeta.name, len(ids), n_val, len(train), len(val))
    return train, val


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--alto-minimo", type=int, default=15)
    parser.add_argument("--max-carro", type=int, default=30, help="Recortes por carro")
    parser.add_argument("--max-moto", type=int, default=80, help="Recortes por moto")
    parser.add_argument("--fraccion-val", type=float, default=0.12)
    args = parser.parse_args()

    train = [(f"ocr/{r['image_path']}", r["plate_text"]) for r in leer_csv(ROBOFLOW / "train.csv")]
    val = [(f"ocr/{r['image_path']}", r["plate_text"]) for r in leer_csv(ROBOFLOW / "valid.csv")]
    logger.info("Roboflow: %d train, %d val", len(train), len(val))
    for carpeta in sorted(p for p in VIDEOS.iterdir() if (p / "vehiculos.csv").exists()):
        t, v = recortes_de_video(carpeta, args.alto_minimo, args.max_carro, args.max_moto,
                                 args.fraccion_val)
        train += t
        val += v
    for nombre, filas in (("train", train), ("val", val)):
        ruta = RAIZ / f"ocr_combinado_{nombre}.csv"
        with open(ruta, "w", newline="", encoding="utf-8") as f:
            escritor = csv.writer(f)
            escritor.writerow(["image_path", "plate_text"])
            escritor.writerows(filas)
        motos = sum(1 for _, p in filas if REGEX_MOTO.match(p))
        logger.info("%s: %d recortes (%d de moto)", ruta, len(filas), motos)


if __name__ == "__main__":
    main()
