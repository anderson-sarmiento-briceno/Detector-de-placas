"""Descarga datasets públicos de Roboflow Universe en formato YOLO a data/datasets/.

Requiere ROBOFLOW_API_KEY en el archivo .env (cuenta gratuita de Roboflow).

Uso:
    python -m scripts.descargar_dataset                  # todos los de DATASETS
    python -m scripts.descargar_dataset --solo caracteres

Datasets (todos de placas colombianas):
- caracteres: helian/placa_colombia v7 (CC BY 4.0). Caja de la placa + cada carácter
  etiquetado (0-9, A-Z) → sirve para entrenar el OCR y el detector.
- placas_anajmr: anajmr/placas-e7lfl v2 (CC BY 4.0). Solo la caja de la placa.
"""
import argparse
import io
import logging
import os
import time
import zipfile
from pathlib import Path

import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

URL_API = "https://api.roboflow.com"
CARPETA_DATASETS = Path("data/datasets")
FORMATO = "yolov8"

# nombre local → (workspace/proyecto, versión)
DATASETS = {
    "caracteres": ("helian/placa_colombia", 7),
    "placas_anajmr": ("anajmr/placas-e7lfl", 2),
}


def obtener_clave() -> str:
    load_dotenv()
    clave = os.getenv("ROBOFLOW_API_KEY", "").strip().strip("\"'")
    if not clave:
        raise SystemExit("Falta ROBOFLOW_API_KEY en el archivo .env (ver .env.example)")
    return clave


def enlace_exportacion(proyecto: str, version: int, clave: str) -> str:
    """Pide a Roboflow el zip de la versión; si aún lo está generando, espera."""
    url = f"{URL_API}/{proyecto}/{version}/{FORMATO}"
    for _ in range(60):
        r = requests.get(url, params={"api_key": clave}, timeout=60)
        r.raise_for_status()
        datos = r.json()
        if "export" in datos and datos["export"].get("link"):
            return datos["export"]["link"]
        logger.info("Roboflow está preparando la exportación de %s v%d...", proyecto, version)
        time.sleep(5)
    raise TimeoutError(f"Roboflow no terminó de exportar {proyecto} v{version}")


def descargar(nombre: str, clave: str) -> Path:
    proyecto, version = DATASETS[nombre]
    destino = CARPETA_DATASETS / nombre
    if destino.exists():
        logger.info("%s ya existe, se omite (bórralo para volver a descargar)", destino)
        return destino
    enlace = enlace_exportacion(proyecto, version, clave)
    logger.info("Descargando %s v%d...", proyecto, version)
    r = requests.get(enlace, timeout=600)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        z.extractall(destino)
    logger.info("%s → %s", proyecto, destino)
    return destino


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--solo", choices=DATASETS, help="Descargar solo este dataset")
    args = parser.parse_args()

    clave = obtener_clave()
    for nombre in [args.solo] if args.solo else DATASETS:
        descargar(nombre, clave)


if __name__ == "__main__":
    main()
