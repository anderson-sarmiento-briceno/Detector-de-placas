"""Carga placas de interés desde un CSV a la base de datos.

Uso: python -m scripts.cargar_placas placas.csv

El CSV debe tener encabezado con las columnas `placa` y (opcional) `motivo`:
    placa,motivo
    ABC123,Vehículo reportado
    XYZ12D,Moto de prueba
"""
import argparse
import csv
import logging

from src.config import cargar_config
from src.database import BaseDatos
from src.plate_utils import normalizar

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv", help="Archivo CSV con columnas placa,motivo")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    bd = BaseDatos(cargar_config(args.config)["ruta_bd"])
    cargadas = 0
    with open(args.csv, newline="", encoding="utf-8-sig") as f:
        for fila in csv.DictReader(f):
            placa = normalizar(fila.get("placa", ""))
            if not placa:
                logger.warning("Fila sin placa, se omite: %s", fila)
                continue
            bd.agregar_placa(placa, (fila.get("motivo") or "").strip())
            cargadas += 1
    logger.info("Placas cargadas: %d (total en la BD: %d)", cargadas, bd.contar_placas())
    bd.cerrar()


if __name__ == "__main__":
    main()
