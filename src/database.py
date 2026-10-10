"""Acceso a la base de datos SQLite de placas de interés y detecciones."""
import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

ESQUEMA = """
CREATE TABLE IF NOT EXISTS placas_interes (
    placa       TEXT PRIMARY KEY,   -- normalizada, ej. ABC123
    motivo      TEXT,               -- descripción libre
    creado_en   TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS detecciones (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    video        TEXT,
    frame        INTEGER,
    segundo      REAL,
    placa        TEXT,
    confianza    REAL,
    coincidencia INTEGER            -- 0/1
);
"""


class BaseDatos:
    def __init__(self, ruta: str | Path) -> None:
        Path(ruta).parent.mkdir(parents=True, exist_ok=True)
        self.conexion = sqlite3.connect(ruta)
        self.conexion.executescript(ESQUEMA)
        logger.info("Base de datos: %s (%d placas de interés)", ruta, self.contar_placas())

    def contar_placas(self) -> int:
        return self.conexion.execute("SELECT COUNT(*) FROM placas_interes").fetchone()[0]

    def buscar(self, placa: str) -> str | None:
        """Si la placa está en la lista de interés devuelve su motivo (o ''), si no None."""
        fila = self.conexion.execute(
            "SELECT motivo FROM placas_interes WHERE placa = ?", (placa,)).fetchone()
        return None if fila is None else (fila[0] or "")

    def agregar_placa(self, placa: str, motivo: str = "") -> None:
        self.conexion.execute(
            "INSERT OR REPLACE INTO placas_interes (placa, motivo) VALUES (?, ?)", (placa, motivo))
        self.conexion.commit()

    def registrar_deteccion(self, video: str, frame: int, segundo: float, placa: str,
                            confianza: float, coincidencia: bool) -> None:
        self.conexion.execute(
            "INSERT INTO detecciones (video, frame, segundo, placa, confianza, coincidencia) "
            "VALUES (?, ?, ?, ?, ?, ?)", (video, frame, segundo, placa, confianza, int(coincidencia)))
        self.conexion.commit()

    def cerrar(self) -> None:
        self.conexion.close()
