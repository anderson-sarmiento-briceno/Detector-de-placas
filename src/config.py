"""Carga de la configuración desde config.yaml."""
from pathlib import Path
from typing import Any

import yaml

RUTA_CONFIG_POR_DEFECTO = Path("config.yaml")


def cargar_config(ruta: Path = RUTA_CONFIG_POR_DEFECTO) -> dict[str, Any]:
    """Lee el YAML de configuración y lo devuelve como diccionario."""
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f)
