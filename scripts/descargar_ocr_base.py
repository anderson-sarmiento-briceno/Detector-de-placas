"""Descarga los pesos entrenables (.keras) de los OCR globales de fast-plate-ocr (MIT).

Sirven de punto de partida para afinar el OCR con placas colombianas.
Destino: models/ocr_base/<variante>/ (pesos .keras + model_config.yaml + plate_config.yaml)

Uso:
    python -m scripts.descargar_ocr_base               # variantes s y xs
    python -m scripts.descargar_ocr_base --variantes xs
"""
import argparse
import logging
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

URL_BASE = "https://github.com/ankandrew/cnn-ocr-lp/releases/download/arg-plates"
CARPETA = Path("models/ocr_base")
ARCHIVOS = {  # sufijo en el release → nombre local
    ".keras": "modelo.keras",
    "_model_config.yaml": "model_config.yaml",
    "_plate_config.yaml": "plate_config.yaml",
}


def descargar(variante: str) -> None:
    destino = CARPETA / variante
    destino.mkdir(parents=True, exist_ok=True)
    for sufijo, nombre_local in ARCHIVOS.items():
        ruta = destino / nombre_local
        if ruta.exists():
            continue
        url = f"{URL_BASE}/cct_{variante}_v2_global{sufijo}"
        logger.info("Descargando %s", url)
        urllib.request.urlretrieve(url, ruta)
    logger.info("OCR base cct-%s-v2 en %s", variante, destino)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--variantes", nargs="+", default=["s", "xs"], choices=["s", "xs"])
    args = parser.parse_args()
    for variante in args.variantes:
        descargar(variante)


if __name__ == "__main__":
    main()
