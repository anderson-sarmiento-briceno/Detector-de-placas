"""Descarga un detector de placas preentrenado desde Hugging Face a models/.

Uso:
    python -m scripts.descargar_modelo                       # genérico nano → models/detector_placas.pt
    python -m scripts.descargar_modelo --modelo colombia     # colombiano  → models/detector_colombia.pt
    python -m scripts.descargar_modelo --variante s          # genérico más grande

Modelos:
- generico: morsetechlab/yolov11-license-plate-detection (YOLOv11, placas de varios países, AGPL-3.0)
- colombia: Rotsen2/detector-placas-colombia (YOLOv8n, placas colombianas, Apache-2.0)
"""
import argparse
import logging
import shutil
from pathlib import Path

from huggingface_hub import hf_hub_download

logger = logging.getLogger(__name__)

MODELOS = {
    "generico": ("morsetechlab/yolov11-license-plate-detection",
                 "license-plate-finetune-v1{variante}.pt", Path("models/detector_placas.pt")),
    "colombia": ("Rotsen2/detector-placas-colombia", "best.pt", Path("models/detector_colombia.pt")),
}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--modelo", default="generico", choices=MODELOS)
    parser.add_argument("--variante", default="n", choices=list("nsmlx"),
                        help="Tamaño del modelo genérico (n = nano, el más liviano)")
    args = parser.parse_args()

    repo_id, archivo, destino = MODELOS[args.modelo]
    archivo = archivo.format(variante=args.variante)
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(hf_hub_download(repo_id=repo_id, filename=archivo), destino)
    logger.info("Modelo %s/%s copiado a %s", repo_id, archivo, destino)


if __name__ == "__main__":
    main()
