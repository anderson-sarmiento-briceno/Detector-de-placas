"""Abstracción de la fuente de video.

Hoy solo hay archivo de video; en la Fase 2 se agregará cámara en vivo
implementando la misma interfaz (iterar sobre `Frame`).
"""
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Frame:
    imagen: np.ndarray   # BGR, como lo entrega OpenCV
    numero: int          # índice del frame dentro del video (desde 0)
    segundo: float       # posición en el video, en segundos


class FuenteArchivo:
    """Lee un archivo de video y entrega 1 de cada `cada_n` frames."""

    def __init__(self, ruta: str | Path, cada_n: int = 1) -> None:
        self.ruta = Path(ruta)
        if not self.ruta.exists():
            raise FileNotFoundError(f"No existe el video: {self.ruta}")
        self.cada_n = max(1, cada_n)
        self._cap = cv2.VideoCapture(str(self.ruta))
        if not self._cap.isOpened():
            raise RuntimeError(f"OpenCV no pudo abrir el video: {self.ruta}")
        self.fps: float = self._cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.ancho = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.alto = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.total_frames = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
        logger.info(
            "Video %s: %dx%d, %.1f fps, %d frames (%.1f s)",
            self.ruta.name, self.ancho, self.alto, self.fps,
            self.total_frames, self.total_frames / self.fps,
        )

    def __iter__(self) -> Iterator[Frame]:
        numero = 0
        while True:
            # grab() avanza sin decodificar: más rápido para los frames saltados
            if not self._cap.grab():
                break
            if numero % self.cada_n == 0:
                ok, imagen = self._cap.retrieve()
                if not ok:
                    break
                yield Frame(imagen, numero, numero / self.fps)
            numero += 1

    def cerrar(self) -> None:
        self._cap.release()

    def __enter__(self) -> "FuenteArchivo":
        return self

    def __exit__(self, *_: object) -> None:
        self.cerrar()
