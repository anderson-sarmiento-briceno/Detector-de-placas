"""Recorte, preprocesado y OCR de la placa."""
import logging

import cv2
import easyocr
import numpy as np

from src.detector import Deteccion

logger = logging.getLogger(__name__)

CARACTERES_PERMITIDOS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"


def recortar(imagen: np.ndarray, d: Deteccion, margen: float) -> np.ndarray:
    """Recorta la caja agregando un margen proporcional a su tamaño, sin salirse de la imagen."""
    alto_img, ancho_img = imagen.shape[:2]
    mx = int((d.x2 - d.x1) * margen)
    my = int((d.y2 - d.y1) * margen)
    x1, y1 = max(0, d.x1 - mx), max(0, d.y1 - my)
    x2, y2 = min(ancho_img, d.x2 + mx), min(alto_img, d.y2 + my)
    return imagen[y1:y2, x1:x2]


def preprocesar(recorte: np.ndarray, alto_objetivo: int) -> np.ndarray:
    """Escala de grises, redimensiona a una altura fija y mejora el contraste con CLAHE."""
    gris = cv2.cvtColor(recorte, cv2.COLOR_BGR2GRAY)
    escala = alto_objetivo / gris.shape[0]
    gris = cv2.resize(gris, None, fx=escala, fy=escala, interpolation=cv2.INTER_CUBIC)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gris)


class LectorOCR:
    def __init__(self, usar_gpu: bool, margen: float, alto_objetivo: int) -> None:
        logger.info("Cargando EasyOCR (la primera vez descarga sus modelos)...")
        self.reader = easyocr.Reader(["en"], gpu=usar_gpu, verbose=False)
        self.margen = margen
        self.alto_objetivo = alto_objetivo

    def leer(self, imagen: np.ndarray, d: Deteccion) -> tuple[str, float]:
        """Devuelve (texto crudo, confianza) de la línea principal de la placa.

        La línea principal es la de letras más grandes: así se ignoran textos
        pequeños como el municipio o el nombre del estado/país.
        """
        recorte = preprocesar(recortar(imagen, d, self.margen), self.alto_objetivo)
        resultados = self.reader.readtext(recorte, allowlist=CARACTERES_PERMITIDOS)
        if not resultados:
            return "", 0.0
        _, texto, conf = max(resultados, key=lambda r: r[0][2][1] - r[0][0][1])
        return texto, float(conf)
