"""Saca recortes de placa etiquetados de un video, para reentrenar el OCR.

Corre detector + seguimiento + OCR + votación como el programa principal, pero guarda el
recorte de cada detección. Al final, todos los recortes de un vehículo reciben la placa que
ganó la votación: así un mismo vehículo aporta decenas de ejemplos (lejos, cerca, borroso,
inclinado) con la etiqueta correcta, incluidos los frames donde el OCR leyó mal.
Después una persona revisa una imagen por vehículo (scripts.revisar_placas_video).

Salida en --destino/<video>/:
    recortes/<track>_<frame>.jpg   recorte de cada detección (con el margen del pipeline)
    recortes.csv                   recorte, track_id, segundo, alto_px, lectura, confianza, vehiculo
    vehiculos.csv                  track_id, placa, lecturas, segundo, mejor_recorte, decision

Uso:
    python -m scripts.recortes_ocr_video --video data/videos/x.mp4 --excluir 590-910
"""
import argparse
import csv
import logging
from functools import partial
from pathlib import Path

import cv2

from src.config import cargar_config
from src.detector import DetectorPlacas
from src.ocr import LectorONNX, recortar
from src.plate_utils import validar_placa
from src.tracker import VotacionPlacas
from src.video_source import FuenteArchivo

logger = logging.getLogger(__name__)

ALTO_MINIMO_RECORTE_PX = 15   # más bajos no los lee ni una persona


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--destino", type=Path, default=Path("data/datasets/ocr_video"))
    parser.add_argument("--excluir", action="append", default=[],
                        help="Tramo reservado para prueba, en segundos 'inicio-fin' (se puede repetir)")
    args = parser.parse_args()
    excluidos = [tuple(map(float, t.split("-"))) for t in args.excluir]

    config = cargar_config("config.yaml")
    detector = DetectorPlacas(config["modelo_detector"], config["confianza_minima_deteccion"],
                              ALTO_MINIMO_RECORTE_PX, config["tracker"])
    lector = LectorONNX(config["modelo_ocr"], config["config_modelo_ocr"], config["margen_recorte"])
    validar = partial(validar_placa, formato=config["formato_placa"])
    votacion = VotacionPlacas(config["votos_minimos_para_confirmar"], validar,
                              config["segundos_fusion_vehiculos"], config.get("segundos_fusion_misma_placa"))

    carpeta = args.destino / args.video.stem
    (carpeta / "recortes").mkdir(parents=True, exist_ok=True)
    filas = []
    with FuenteArchivo(args.video, config["procesar_cada_n_frames"]) as fuente:
        for frame in fuente:
            if any(ini <= frame.segundo <= fin for ini, fin in excluidos):
                detector.reiniciar_seguimiento()
                continue
            for d in detector.detectar(frame.imagen):
                if d.track_id is None:
                    continue
                texto, conf = lector.leer(frame.imagen, d)
                placa = validar(texto) if conf >= config["confianza_minima_ocr"] else None
                if placa:
                    votacion.agregar(d.track_id, placa, conf, frame.numero, frame.segundo)
                nombre = f"{d.track_id}_{frame.numero}.jpg"
                cv2.imwrite(str(carpeta / "recortes" / nombre), recortar(frame.imagen, d, config["margen_recorte"]))
                filas.append({"recorte": nombre, "track_id": d.track_id, "segundo": round(frame.segundo, 2),
                              "alto_px": d.alto, "lectura": texto, "confianza": round(conf, 3)})
            if frame.numero % 3000 == 0:
                logger.info("%.0f s procesados, %d recortes", frame.segundo, len(filas))

    # Un vehículo por placa confirmada; su mejor recorte = el más alto (más cercano).
    # Cada recorte se asocia al vehículo final (los track_id fusionados apuntan al mismo).
    vehiculos = {}
    for fila in filas:
        v = votacion.vehiculo_de(fila["track_id"])
        fila["vehiculo"] = v.track_id if v is not None and v.placa_confirmada else ""
        if not fila["vehiculo"]:
            continue
        actual = vehiculos.get(v.track_id)
        if actual is None or fila["alto_px"] > actual["alto_px"]:
            vehiculos[v.track_id] = {"track_id": v.track_id, "placa": v.placa_confirmada,
                                     "lecturas": len(v.lecturas), "segundo": v.primer_segundo,
                                     "mejor_recorte": fila["recorte"], "alto_px": fila["alto_px"],
                                     "decision": ""}
    with open(carpeta / "recortes.csv", "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=list(filas[0]))
        escritor.writeheader()
        escritor.writerows(filas)
    with open(carpeta / "vehiculos.csv", "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=["track_id", "placa", "lecturas", "segundo",
                                                 "mejor_recorte", "alto_px", "decision"])
        escritor.writeheader()
        escritor.writerows(sorted(vehiculos.values(), key=lambda v: v["segundo"]))
    logger.info("%d recortes, %d vehículos con placa confirmada → %s", len(filas), len(vehiculos), carpeta)


if __name__ == "__main__":
    main()
