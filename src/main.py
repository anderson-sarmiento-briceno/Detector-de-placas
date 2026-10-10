"""Punto de entrada: python -m src.main [--video ruta.mp4 | carpeta]"""
import argparse
import csv
import logging
import time
from functools import partial
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from src.alerts import alertar
from src.config import cargar_config
from src.database import BaseDatos
from src.detector import Deteccion, DetectorPlacas
from src.ocr import LectorOCR
from src.plate_utils import validar_placa
from src.tracker import Vehiculo, VotacionPlacas
from src.video_source import FuenteArchivo, buscar_videos

logger = logging.getLogger(__name__)

TECLA_SALIR = ord("q")
TECLA_PAUSA = ord(" ")
VERDE = (0, 255, 0)
AMARILLO = (0, 220, 255)
ROJO = (0, 0, 255)
CARPETA_SALIDA = Path("outputs")
COLUMNAS_LOG = ["video", "frame", "segundo", "track_id", "placa_leida", "confianza_ocr",
                "placa_confirmada", "coincidencia"]


def parsear_argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lector de placas desde video")
    parser.add_argument("--video", help="Video o carpeta de videos (por defecto, la de config.yaml)")
    parser.add_argument("--config", default="config.yaml", help="Ruta de config.yaml")
    return parser.parse_args()


def dibujar(imagen: np.ndarray, d: Deteccion, etiqueta: str, color: tuple[int, int, int]) -> None:
    cv2.rectangle(imagen, (d.x1, d.y1), (d.x2, d.y2), color, 2)
    cv2.putText(imagen, etiqueta, (d.x1, max(20, d.y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)


class Pipeline:
    """Une detector, OCR, votación, BD y alertas para procesar videos."""

    def __init__(self, config: dict[str, Any], log_csv: csv.DictWriter) -> None:
        self.config = config
        self.log_csv = log_csv
        self.detector = DetectorPlacas(config["modelo_detector"], config["confianza_minima_deteccion"],
                                       config["alto_minimo_caja_px"], config["tracker"])
        self.lector = LectorOCR(config["ocr_usar_gpu"], config["margen_recorte"],
                                config["alto_recorte_ocr_px"], config["proporcion_alto_linea_ocr"])
        self.bd = BaseDatos(config["ruta_bd"])
        self.validar = partial(validar_placa, formato=config["formato_placa"])

    def procesar_video(self, ruta_video: Path) -> tuple[VotacionPlacas, set[int], bool]:
        """Procesa un video. Devuelve (votación, track_ids con alerta, si el usuario pidió salir)."""
        config = self.config
        votacion = VotacionPlacas(config["votos_minimos_para_confirmar"], self.validar,
                                  config["segundos_fusion_vehiculos"])
        con_alerta: set[int] = set()   # track_id (del vehículo) cuya placa actual está en la BD
        reportadas: dict[int, str] = {}  # última placa mostrada en consola por vehículo
        salir = False
        procesados = 0
        escritor: cv2.VideoWriter | None = None
        ruta_salida = CARPETA_SALIDA / f"{ruta_video.stem}_procesado.mp4"
        self.detector.reiniciar_seguimiento()
        inicio = time.perf_counter()
        with FuenteArchivo(ruta_video, config["procesar_cada_n_frames"]) as fuente:
            if config["guardar_video_salida"]:
                ruta_salida.parent.mkdir(parents=True, exist_ok=True)
                escritor = cv2.VideoWriter(str(ruta_salida), cv2.VideoWriter_fourcc(*"mp4v"),
                                           fuente.fps / fuente.cada_n, (fuente.ancho, fuente.alto))

            for frame in fuente:
                procesados += 1
                for d in self.detector.detectar(frame.imagen):
                    texto_crudo, conf_ocr = self.lector.leer(frame.imagen, d)
                    placa = self.validar(texto_crudo)
                    if placa and d.track_id is not None:
                        vehiculo, cambio = votacion.agregar(d.track_id, placa, conf_ocr,
                                                            frame.numero, frame.segundo)
                        if cambio:
                            self._placa_cambio(vehiculo, reportadas, con_alerta, ruta_video.name)
                        self.log_csv.writerow({
                            "video": ruta_video.name, "frame": frame.numero,
                            "segundo": round(frame.segundo, 2), "track_id": vehiculo.track_id,
                            "placa_leida": placa, "confianza_ocr": round(conf_ocr, 3),
                            "placa_confirmada": vehiculo.placa_confirmada or "",
                            "coincidencia": int(vehiculo.track_id in con_alerta)})
                    logger.debug("Frame %d track %s: %r → %s", frame.numero, d.track_id, texto_crudo, placa)

                    vehiculo = votacion.vehiculo_de(d.track_id)
                    if vehiculo and vehiculo.placa_confirmada:
                        color = ROJO if vehiculo.track_id in con_alerta else VERDE
                        dibujar(frame.imagen, d, vehiculo.placa_confirmada, color)
                    else:
                        dibujar(frame.imagen, d, f"? {placa or texto_crudo}", AMARILLO)

                cv2.putText(frame.imagen, f"frame {frame.numero}  {frame.segundo:.1f}s",
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, VERDE, 2)
                if escritor:
                    escritor.write(frame.imagen)
                if config["mostrar_ventana"]:
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

        # En la BD queda una fila por vehículo, con su placa final
        for v in votacion.confirmados():
            self.bd.registrar_deteccion(ruta_video.name, v.primer_frame, v.primer_segundo,
                                        v.placa_confirmada, v.confianza, v.track_id in con_alerta)
        return votacion, con_alerta, salir

    def _placa_cambio(self, vehiculo: Vehiculo, reportadas: dict[int, str], con_alerta: set[int],
                      video: str) -> None:
        """La placa de un vehículo se confirmó o se corrigió: avisar y consultar la BD."""
        placa = vehiculo.placa_confirmada
        anterior = reportadas.get(vehiculo.track_id)
        reportadas[vehiculo.track_id] = placa
        if anterior is None:
            logger.info("✅ Placa confirmada %s  (vehículo %d, %d lecturas, %.1fs)",
                        placa, vehiculo.track_id, len(vehiculo.lecturas), vehiculo.ultimo_segundo)
        else:
            logger.info("🔁 Placa corregida %s → %s  (vehículo %d, %d lecturas)",
                        anterior, placa, vehiculo.track_id, len(vehiculo.lecturas))

        motivo = self.bd.buscar(placa)
        if motivo is None:
            con_alerta.discard(vehiculo.track_id)
        elif vehiculo.track_id not in con_alerta:
            con_alerta.add(vehiculo.track_id)
            alertar(placa, motivo, video, vehiculo.ultimo_segundo, self.config["sonido_alerta"])


def imprimir_resumen(nombre_video: str, votacion: VotacionPlacas, con_alerta: set[int]) -> None:
    confirmados = votacion.confirmados()
    print(f"\n=== Placas confirmadas en {nombre_video}: {len(confirmados)} ===")
    if not confirmados:
        print("  (ninguna)")
    for v in confirmados:
        marca = "  🚨 ALERTA" if v.track_id in con_alerta else ""
        print(f"  {v.placa_confirmada}   {v.primer_segundo:6.1f}s   {len(v.lecturas):3d} lecturas{marca}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args = parsear_argumentos()
    config = cargar_config(args.config)
    # Se buscan los videos antes de cargar los modelos, para fallar rápido si no hay ninguno
    videos = buscar_videos(args.video or config["video"])
    logger.info("Videos a procesar (%d): %s", len(videos), ", ".join(v.name for v in videos))

    ruta_log = Path(config["ruta_log"])
    ruta_log.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta_log, "w", newline="", encoding="utf-8") as f:
        log_csv = csv.DictWriter(f, fieldnames=COLUMNAS_LOG)
        log_csv.writeheader()
        pipeline = Pipeline(config, log_csv)
        for ruta_video in videos:
            votacion, con_alerta, salir = pipeline.procesar_video(ruta_video)
            imprimir_resumen(ruta_video.name, votacion, con_alerta)
            if salir:
                break
        pipeline.bd.cerrar()
    logger.info("Log de lecturas: %s", ruta_log)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
