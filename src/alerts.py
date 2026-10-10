"""Cómo se notifica una coincidencia con la lista de placas de interés."""
import logging
import sys

logger = logging.getLogger(__name__)


def alertar(placa: str, motivo: str, video: str, segundo: float, sonido: bool) -> None:
    """Avisa en consola (y con un pitido opcional) que se vio una placa de interés."""
    logger.warning("🚨 ALERTA  %s  en %s (%.1fs)  motivo: %s", placa, video, segundo, motivo or "-")
    if sonido and sys.platform == "win32":
        import winsound
        winsound.Beep(1000, 300)
