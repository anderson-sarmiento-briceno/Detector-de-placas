"""Punto de entrada: python -m src.main [--video ruta.mp4 | carpeta]"""
import argparse
import logging
import time
from collections import Counter
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from src.config import cargar_config
from src.detector import Deteccion, DetectorPlacas
from src.ocr import LectorOCR
from src.plate_utils import validar_placa
from src.video_source import FuenteArchivo, buscar_videos

logger = logging.getLogger(__name__)

TECLA_SALIR = ord("q")
TECLA_PAUSA = ord(" ")
VERDE = (0, 255, 0)
AMARILLO = (0, 220, 255)
CARPETA_SALIDA = Path("outputs")


def parsear_argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lector de placas desde video")
    parser.add_argument("--video", help="Video o carpeta de videos (por defecto, la de config.yaml)")
    parser.add_argument("--config", default="config.yaml", help="Ruta de config.yaml")
    return parser.parse_args()


def dibujar(imagen: np.ndarray, d: Deteccion, etiqueta: str, color: tuple[int, int, int]) -> None:
    cv2.rectangle(imagen, (d.x1, d.y1), (d.x2, d.y2), color, 2)
    cv2.putText(imagen, etiqueta, (d.x1, max(20, d.y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)


def procesar_video(ruta_video: Path, config: dict[str, Any], detector: DetectorPlacas,
                   lector: LectorOCR) -> tuple[Counter[str], bool]:
    """Procesa un video. Devuelve (placas leídas y cuántas veces, si el usuario pidió salir)."""
    mostrar = config["mostrar_ventana"]
    formato = config["formato_placa"]
    placas_vistas: Counter[str] = Counter()
    salir = False
    procesados = 0
    escritor: cv2.VideoWriter | None = None
    ruta_salida = CARPETA_SALIDA / f"{ruta_video.stem}_procesado.mp4"
    inicio = time.perf_counter()
    with FuenteArchivo(ruta_video, config["procesar_cada_n_frames"]) as fuente:
        if config["guardar_video_salida"]:
            ruta_salida.parent.mkdir(parents=True, exist_ok=True)
            escritor = cv2.VideoWriter(str(ruta_salida), cv2.VideoWriter_fourcc(*"mp4v"),
                                       fuente.fps / fuente.cada_n, (fuente.ancho, fuente.alto))

        for frame in fuente:
            procesados += 1
            for d in detector.detectar(frame.imagen):
                texto_crudo, conf_ocr = lector.leer(frame.imagen, d)
                placa = validar_placa(texto_crudo, formato)
                if placa:
                    placas_vistas[placa] += 1
                    logger.info("Frame %d (%.1fs): placa %s  [det %.2f, ocr %.2f]",
                                frame.numero, frame.segundo, placa, d.confianza, conf_ocr)
                    dibujar(frame.imagen, d, placa, VERDE)
                else:
                    logger.debug("Frame %d: lectura descartada %r", frame.numero, texto_crudo)
                    dibujar(frame.imagen, d, f"? {texto_crudo}", AMARILLO)

            cv2.putText(frame.imagen, f"frame {frame.numero}  {frame.segundo:.1f}s",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, VERDE, 2)
            if escritor:
                escritor.write(frame.imagen)
            if mostrar:
                cv2.imshow("Lector de placas", frame.imagen)
                tecla = cv2.waitKey(1) & 0xFF
                if tecla == TECLA_SALIR:
                    logger.info("Detenido por el usuario")
                    salir = True
                    break
                if tecla == TECLA_PAUSA:
                    cv2.waitKey(0)

    if escritor:
        escritor.release()
        logger.info("Video de salida: %s", ruta_salida)
    duracion = time.perf_counter() - inicio
    logger.info("Frames procesados: %d en %.1f s (%.1f FPS)", procesados, duracion, procesados / duracion)
    return placas_vistas, salir


def imprimir_resumen(nombre_video: str, placas_vistas: Counter[str]) -> None:
    print(f"\n=== Placas encontradas en {nombre_video} (placa: veces leída) ===")
    if not placas_vistas:
        print("  (ninguna)")
    for placa, veces in placas_vistas.most_common():
        print(f"  {placa}: {veces}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args = parsear_argumentos()
    config = cargar_config(args.config)
    # Se buscan los videos antes de cargar los modelos, para fallar rápido si no hay ninguno
    videos = buscar_videos(args.video or config["video"])
    logger.info("Videos a procesar (%d): %s", len(videos), ", ".join(v.name for v in videos))

    detector = DetectorPlacas(config["modelo_detector"], config["confianza_minima_deteccion"],
                              config["alto_minimo_caja_px"])
    lector = LectorOCR(config["ocr_usar_gpu"], config["margen_recorte"], config["alto_recorte_ocr_px"],
                       config["proporcion_alto_linea_ocr"])

    for ruta_video in videos:
        placas_vistas, salir = procesar_video(ruta_video, config, detector, lector)
        imprimir_resumen(ruta_video.name, placas_vistas)
        if salir:
            break
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
