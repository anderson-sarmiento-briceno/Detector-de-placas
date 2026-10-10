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
    def __init__(self, usar_gpu: bool, margen: float, alto_objetivo: int,
                 proporcion_alto_linea: float) -> None:
        logger.info("Cargando EasyOCR (la primera vez descarga sus modelos)...")
        self.reader = easyocr.Reader(["en"], gpu=usar_gpu, verbose=False)
        self.margen = margen
        self.alto_objetivo = alto_objetivo
        self.proporcion_alto_linea = proporcion_alto_linea

    def leer(self, imagen: np.ndarray, d: Deteccion) -> tuple[str, float]:
        """Devuelve (texto crudo, confianza) de la placa.

        Se quedan solo los textos grandes (≥ `proporcion_alto_linea` del más alto):
        así se ignoran textos pequeños como el municipio. Los que quedan se unen en
        orden de lectura (arriba→abajo, izquierda→derecha), lo que cubre las placas
        de moto en dos líneas (ABC / 12D) y los textos que el OCR parte en dos.
        """
        recorte = preprocesar(recortar(imagen, d, self.margen), self.alto_objetivo)
        resultados = self.reader.readtext(recorte, allowlist=CARACTERES_PERMITIDOS)
        if not resultados:
            return "", 0.0
        return unir_lineas_grandes(resultados, self.proporcion_alto_linea)


def unir_lineas_grandes(resultados: list, proporcion_alto: float) -> tuple[str, float]:
    """Une los textos de EasyOCR cuyo alto sea al menos `proporcion_alto` del más alto.

    Cada resultado de EasyOCR es (caja de 4 puntos, texto, confianza).
    La confianza devuelta es la mínima de los textos unidos.
    """
    # La caja puede venir girada o con los puntos en otro orden: se usan min/max de los 4 puntos
    def arriba(r) -> float:
        return min(p[1] for p in r[0])

    def izquierda(r) -> float:
        return min(p[0] for p in r[0])

    def alto(r) -> float:
        return max(p[1] for p in r[0]) - arriba(r)

    alto_max = max(alto(r) for r in resultados)
    if alto_max <= 0:
        return "", 0.0
    grandes = [r for r in resultados if alto(r) >= proporcion_alto * alto_max]
    # Fila = posición vertical en "unidades de alto de línea"; dentro de la fila, por x
    grandes.sort(key=lambda r: (round(arriba(r) / alto_max), izquierda(r)))
    texto = "".join(r[1] for r in grandes)
    return texto, float(min(r[2] for r in grandes))
