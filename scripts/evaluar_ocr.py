"""Compara lectores OCR sobre recortes de placa etiquetados (CSV image_path, plate_text).

Mide, por lector:
- exacta_cruda:    la lectura cruda (normalizada) es igual a la placa real.
- exacta_validada: tras validar_placa('colombia') (corrección por posición) es igual a la real.
- descartadas:     lecturas que la validación rechaza (no cumplen el formato).
- ms_por_placa:    tiempo medio de lectura en este PC.

Uso:
    python -m scripts.evaluar_ocr --csv data/datasets/ocr/test.csv
    python -m scripts.evaluar_ocr --csv ... --lectores easyocr cct-xs-v2-global-model
    python -m scripts.evaluar_ocr --csv ... --onnx models/ocr_colombia.onnx --config models/ocr_colombia.yaml
"""
import argparse
import csv
import logging
import time
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

from src.plate_utils import FORMATO_COLOMBIA, normalizar, validar_placa

logger = logging.getLogger(__name__)

Lector = Callable[[np.ndarray], str]  # recorte BGR → texto crudo

LECTORES_POR_DEFECTO = ["easyocr", "cct-xs-v2-global-model", "cct-s-v2-global-model"]


def lector_easyocr() -> Lector:
    """El OCR actual del pipeline: mismo preprocesado y unión de líneas que src/ocr.py."""
    import easyocr

    from src.ocr import CARACTERES_PERMITIDOS, preprocesar, unir_lineas_grandes

    reader = easyocr.Reader(["en"], gpu=False, verbose=False)

    def leer(recorte: np.ndarray) -> str:
        resultados = reader.readtext(preprocesar(recorte, 100), allowlist=CARACTERES_PERMITIDOS)
        return unir_lineas_grandes(resultados, 0.6)[0] if resultados else ""

    return leer


def lector_fast_plate_ocr(modelo_hub: str | None = None, onnx: Path | None = None,
                          config: Path | None = None) -> Lector:
    from fast_plate_ocr import LicensePlateRecognizer

    reconocedor = LicensePlateRecognizer(hub_ocr_model=modelo_hub, onnx_model_path=onnx,
                                         plate_config_path=config, device="cpu")
    rgb = reconocedor.config.image_color_mode == "rgb"

    def leer(recorte: np.ndarray) -> str:
        imagen = cv2.cvtColor(recorte, cv2.COLOR_BGR2RGB if rgb else cv2.COLOR_BGR2GRAY)
        return reconocedor.run_one(imagen).plate

    return leer


def evaluar(leer: Lector, muestras: list[tuple[np.ndarray, str]]) -> dict:
    cruda = validada = descartadas = 0
    errores = []
    inicio = time.perf_counter()
    for recorte, real in muestras:
        texto = normalizar(leer(recorte))
        placa = validar_placa(texto, FORMATO_COLOMBIA)
        cruda += texto == real
        validada += placa == real
        descartadas += placa is None
        if placa != real and len(errores) < 8:
            errores.append(f"{real}→{texto or '∅'}")
    n = len(muestras)
    return {
        "exacta_cruda": f"{cruda / n:.1%}",
        "exacta_validada": f"{validada / n:.1%}",
        "descartadas": f"{descartadas / n:.1%}",
        "ms_por_placa": round((time.perf_counter() - inicio) * 1000 / n, 1),
        "ejemplos_error": ", ".join(errores),
    }


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--lectores", nargs="*", default=LECTORES_POR_DEFECTO,
                        help="'easyocr' o nombres de modelos del hub de fast-plate-ocr")
    parser.add_argument("--onnx", type=Path, help="Modelo OCR propio (.onnx)")
    parser.add_argument("--config", type=Path, help="plate_config .yaml del modelo propio")
    args = parser.parse_args()

    with open(args.csv, encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    muestras = [(cv2.imread(str(args.csv.parent / r["image_path"])), r["plate_text"]) for r in filas]
    print(f"{len(muestras)} placas de {args.csv}")

    lectores: dict[str, Lector] = {}
    for nombre in args.lectores:
        lectores[nombre] = lector_easyocr() if nombre == "easyocr" else lector_fast_plate_ocr(nombre)
    if args.onnx:
        lectores[args.onnx.stem] = lector_fast_plate_ocr(onnx=args.onnx, config=args.config)

    for nombre, leer in lectores.items():
        print(f"\n== {nombre}")
        for clave, valor in evaluar(leer, muestras).items():
            print(f"  {clave}: {valor}")


if __name__ == "__main__":
    main()
