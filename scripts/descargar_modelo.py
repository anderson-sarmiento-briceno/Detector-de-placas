"""Descarga el detector de placas preentrenado desde Hugging Face a la ruta de config.yaml.

Uso: python -m scripts.descargar_modelo [--variante n|s|m|l|x]
Modelo: morsetechlab/yolov11-license-plate-detection (YOLOv11, placas genéricas, AGPL-3.0).
"""
import argparse
import logging
import shutil
from pathlib import Path

from huggingface_hub import hf_hub_download

from src.config import cargar_config

REPO_ID = "morsetechlab/yolov11-license-plate-detection"

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variante", default="n", choices=list("nsmlx"),
                        help="Tamaño del modelo (n = nano, el más liviano)")
    args = parser.parse_args()

    destino = Path(cargar_config()["modelo_detector"])
    destino.parent.mkdir(parents=True, exist_ok=True)
    archivo = f"license-plate-finetune-v1{args.variante}.pt"
    ruta_cache = hf_hub_download(repo_id=REPO_ID, filename=archivo)
    shutil.copyfile(ruta_cache, destino)
    logger.info("Modelo %s copiado a %s", archivo, destino)


if __name__ == "__main__":
    main()
