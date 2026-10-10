"""Normalización y validación del texto de una placa según el formato configurado."""
import re

FORMATO_GENERICO = "generico"
FORMATO_COLOMBIA = "colombia"

REGEX_GENERICO = re.compile(r"^[A-Z0-9]{5,8}$")

# Plantillas colombianas: L = letra, N = número
PLANTILLA_CARRO = "LLLNNN"   # ABC123
PLANTILLA_MOTO = "LLLNNL"    # ABC12D
REGEX_CARRO = re.compile(r"^[A-Z]{3}[0-9]{3}$")
REGEX_MOTO = re.compile(r"^[A-Z]{3}[0-9]{2}[A-Z]$")

# Confusiones típicas del OCR, corregidas según la posición (solo modo colombia)
A_LETRA = {"0": "O", "1": "I", "5": "S", "8": "B", "2": "Z", "6": "G", "4": "A"}
A_NUMERO = {"O": "0", "D": "0", "Q": "0", "I": "1", "L": "1", "S": "5",
            "B": "8", "Z": "2", "G": "6", "A": "4"}


def normalizar(texto: str) -> str:
    """Mayúsculas y solo caracteres alfanuméricos (quita espacios, guiones, puntos...)."""
    return re.sub(r"[^A-Z0-9]", "", texto.upper())


def corregir_por_plantilla(texto: str, plantilla: str) -> str:
    """Corrige cada carácter según si en esa posición va letra (L) o número (N)."""
    if len(texto) != len(plantilla):
        return texto
    return "".join(
        A_LETRA.get(c, c) if tipo == "L" else A_NUMERO.get(c, c)
        for c, tipo in zip(texto, plantilla)
    )


def corregir_colombia(texto: str) -> str:
    """Corrección para placa de carro: 3 letras + 3 números."""
    return corregir_por_plantilla(texto, PLANTILLA_CARRO)


def validar_colombia(texto: str) -> str | None:
    """Acepta carro (ABC123) o moto (ABC12D).

    1. Si el texto ya cumple uno de los formatos tal cual, se acepta sin tocarlo.
    2. Si no, se prueba la corrección de carro y luego la de moto.
    """
    if REGEX_CARRO.match(texto) or REGEX_MOTO.match(texto):
        return texto
    for plantilla, regex in ((PLANTILLA_CARRO, REGEX_CARRO), (PLANTILLA_MOTO, REGEX_MOTO)):
        corregido = corregir_por_plantilla(texto, plantilla)
        if regex.match(corregido):
            return corregido
    return None


def validar_placa(texto_crudo: str, formato: str) -> str | None:
    """Devuelve la placa normalizada si es válida para el formato, o None si se descarta."""
    texto = normalizar(texto_crudo)
    if formato == FORMATO_COLOMBIA:
        return validar_colombia(texto)
    if formato == FORMATO_GENERICO:
        return texto if REGEX_GENERICO.match(texto) else None
    raise ValueError(f"formato_placa desconocido: {formato!r} (usar 'generico' o 'colombia')")
