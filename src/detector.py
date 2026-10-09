"""Detección de placas con YOLO."""
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from ultralytics import YOLO

logger = logging.getLogger(__name__)


@dataclass
class Deteccion:
    x1: int
    y1: int
    x2: int
    y2: int
    confianza: float

    @property
    def alto(self) -> int:
        return self.y2 - self.y1


class DetectorPlacas:
    def __init__(self, ruta_modelo: str | Path, confianza_minima: float, alto_minimo: int) -> None:
        if not Path(ruta_modelo).exists():
            raise FileNotFoundError(
                f"No existe el modelo {ruta_modelo}. Ejecuta: python -m scripts.descargar_modelo")
        self.modelo = YOLO(str(ruta_modelo))
        self.confianza_minima = confianza_minima
        self.alto_minimo = alto_minimo
        logger.info("Detector cargado: %s", ruta_modelo)

    def detectar(self, imagen: np.ndarray) -> list[Deteccion]:
        """Devuelve las placas encontradas en la imagen (BGR)."""
        resultado = self.modelo.predict(imagen, conf=self.confianza_minima, verbose=False)[0]
        detecciones = []
        for caja, conf in zip(resultado.boxes.xyxy.tolist(), resultado.boxes.conf.tolist()):
            d = Deteccion(*map(int, caja), confianza=conf)
            # Las cajas muy pequeñas no se pueden leer: se descartan
            if d.alto >= self.alto_minimo:
                detecciones.append(d)
        return detecciones
