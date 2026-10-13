"""Exporta un OCR entrenado (.keras) a ONNX / TFLite / CoreML y lo deja en models/.

Envuelve `fast-plate-ocr export` con un arreglo para Windows: la librería escribe el ONNX
en un NamedTemporaryFile abierto y luego lo reabre, cosa que Windows no permite.

Uso:
    python -m scripts.exportar_ocr --modelo models/ocr_entrenados/s/<fecha>/best.keras
    python -m scripts.exportar_ocr --modelo ... --formato tflite
Salida: models/ocr_colombia.<ext> + models/ocr_colombia_plate_config.yaml
"""
import argparse
import functools
import logging
import os
import shutil
import tempfile
from pathlib import Path

# La exportación usa TensorFlow (tf2onnx / TFLiteConverter); debe fijarse antes de importar keras
os.environ.setdefault("KERAS_BACKEND", "tensorflow")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

logger = logging.getLogger(__name__)

EXTENSIONES = {"onnx": ".onnx", "tflite": ".tflite", "coreml": ".mlpackage"}
NOMBRE_SALIDA = "ocr_colombia"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--modelo", type=Path, required=True, help="best.keras del entrenamiento")
    parser.add_argument("--formato", default="onnx", choices=EXTENSIONES)
    parser.add_argument("--plate-config", type=Path, default=Path("configs/ocr_plate_config.yaml"))
    parser.add_argument("--destino", type=Path, default=Path("models"))
    args = parser.parse_args()

    from fast_plate_ocr.cli import export as modulo_export

    modulo_export.NamedTemporaryFile = functools.partial(tempfile.NamedTemporaryFile, delete_on_close=False)

    with tempfile.TemporaryDirectory() as carpeta_tmp:
        modulo_export.export.main(
            ["-m", str(args.modelo), "-f", args.formato, "--plate-config-file", str(args.plate_config),
             "--save-dir", carpeta_tmp],
            standalone_mode=False,
        )
        generado = next(Path(carpeta_tmp).iterdir())
        args.destino.mkdir(parents=True, exist_ok=True)
        salida = args.destino / f"{NOMBRE_SALIDA}{EXTENSIONES[args.formato]}"
        if salida.is_dir():
            shutil.rmtree(salida)
        shutil.move(generado, salida)
    shutil.copy(args.plate_config, args.destino / f"{NOMBRE_SALIDA}_plate_config.yaml")
    logger.info("OCR exportado: %s (%.1f MB)", salida, tamano_mb(salida))


def tamano_mb(ruta: Path) -> float:
    archivos = [ruta] if ruta.is_file() else [p for p in ruta.rglob("*") if p.is_file()]
    return sum(p.stat().st_size for p in archivos) / 1e6


if __name__ == "__main__":
    main()
