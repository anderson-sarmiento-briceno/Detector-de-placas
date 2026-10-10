"""Detección y seguimiento de placas con YOLO."""
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
    track_id: int | None = None   # mismo número en frames seguidos = mismo vehículo

    @property
    def alto(self) -> int:
        return self.y2 - self.y1


class DetectorPlacas:
    def __init__(self, ruta_modelo: str | Path, confianza_minima: float, alto_minimo: int,
                 tracker: str = "bytetrack.yaml") -> None:
        if not Path(ruta_modelo).exists():
            raise FileNotFoundError(
                f"No existe el modelo {ruta_modelo}. Ejecuta: python -m scripts.descargar_modelo")
        self.modelo = YOLO(str(ruta_modelo))
        self.confianza_minima = confianza_minima
        self.alto_minimo = alto_minimo
        self.tracker = tracker
        logger.info("Detector cargado: %s", ruta_modelo)

    def detectar(self, imagen: np.ndarray) -> list[Deteccion]:
        """Detecta y sigue las placas en la imagen (BGR). Llamar con frames consecutivos."""
        resultado = self.modelo.track(imagen, conf=self.confianza_minima, tracker=self.tracker,
                                      persist=True, verbose=False)[0]
        cajas = resultado.boxes
        ids = cajas.id.int().tolist() if cajas.id is not None else [None] * len(cajas)
        detecciones = []
        for caja, conf, track_id in zip(cajas.xyxy.tolist(), cajas.conf.tolist(), ids):
            d = Deteccion(*map(int, caja), confianza=conf, track_id=track_id)
            # Las cajas muy pequeñas no se pueden leer: se descartan
            if d.alto >= self.alto_minimo:
                detecciones.append(d)
        return detecciones

    def reiniciar_seguimiento(self) -> None:
        """Olvida los vehículos seguidos (llamar al empezar un video nuevo)."""
        predictor = self.modelo.predictor
        for tracker in getattr(predictor, "trackers", None) or []:
            tracker.reset()
