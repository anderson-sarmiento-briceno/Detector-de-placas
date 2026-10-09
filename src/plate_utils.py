"""Normalización y validación del texto de una placa según el formato configurado."""
import re

FORMATO_GENERICO = "generico"
FORMATO_COLOMBIA = "colombia"

REGEX_COLOMBIA = re.compile(r"^[A-Z]{3}[0-9]{3}$")
REGEX_GENERICO = re.compile(r"^[A-Z0-9]{5,8}$")

# Confusiones típicas del OCR, corregidas según la posición (solo modo colombia)
A_LETRA = {"0": "O", "1": "I", "5": "S", "8": "B", "2": "Z", "6": "G", "4": "A"}
A_NUMERO = {"O": "0", "D": "0", "Q": "0", "I": "1", "L": "1", "S": "5",
            "B": "8", "Z": "2", "G": "6", "A": "4"}


def normalizar(texto: str) -> str:
    """Mayúsculas y solo caracteres alfanuméricos (quita espacios, guiones, puntos...)."""
    return re.sub(r"[^A-Z0-9]", "", texto.upper())


def corregir_colombia(texto: str) -> str:
    """Corrige letra/número según la posición: 3 letras + 3 números."""
    if len(texto) != 6:
        return texto
    letras = "".join(A_LETRA.get(c, c) for c in texto[:3])
    numeros = "".join(A_NUMERO.get(c, c) for c in texto[3:])
    return letras + numeros


def validar_placa(texto_crudo: str, formato: str) -> str | None:
    """Devuelve la placa normalizada si es válida para el formato, o None si se descarta."""
    texto = normalizar(texto_crudo)
    if formato == FORMATO_COLOMBIA:
        texto = corregir_colombia(texto)
        return texto if REGEX_COLOMBIA.match(texto) else None
    if formato == FORMATO_GENERICO:
        return texto if REGEX_GENERICO.match(texto) else None
    raise ValueError(f"formato_placa desconocido: {formato!r} (usar 'generico' o 'colombia')")
