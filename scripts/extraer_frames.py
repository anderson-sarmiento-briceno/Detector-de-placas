"""Extrae frames de un video cada N segundos, para armar datasets del detector.

Uso:
    python -m scripts.extraer_frames --video data/videos/x.mp4 --desde 140 --cada 0.5
    python -m scripts.extraer_frames --video ... --desde 0 --hasta 130 --destino data/datasets/detector_video/prueba

Los frames se guardan como <video>_<segundo>.jpg en --destino/images.
"""
import argparse
import logging
from pathlib import Path

import cv2

logger = logging.getLogger(__name__)


def extraer(video: Path, destino: Path, desde: float, hasta: float | None, cada: float) -> int:
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise FileNotFoundError(f"No se pudo abrir {video}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    total = cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps
    hasta = min(hasta or total, total)
    paso = max(1, round(cada * fps))
    carpeta = destino / "images"
    carpeta.mkdir(parents=True, exist_ok=True)
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(desde * fps))
    numero, guardados = int(desde * fps), 0
    while numero / fps < hasta:
        if not cap.grab():
            break
        if numero % paso == 0:
            _, imagen = cap.retrieve()
            cv2.imwrite(str(carpeta / f"{video.stem}_{numero / fps:07.1f}.jpg"), imagen,
                        [cv2.IMWRITE_JPEG_QUALITY, 95])
            guardados += 1
        numero += 1
    cap.release()
    return guardados


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--destino", type=Path, default=Path("data/datasets/detector_video/entrenamiento"))
    parser.add_argument("--desde", type=float, default=0.0, help="Segundo inicial")
    parser.add_argument("--hasta", type=float, help="Segundo final (por defecto, el final del video)")
    parser.add_argument("--cada", type=float, default=0.5, help="Segundos entre frames")
    args = parser.parse_args()
    n = extraer(args.video, args.destino, args.desde, args.hasta, args.cada)
    logger.info("%d frames de %s → %s", n, args.video, args.destino / "images")


if __name__ == "__main__":
    main()
