/// Normalización y validación de placas colombianas.
///
/// Traducción de src/plate_utils.py (modo `colombia`): carro ABC123 y moto ABC12D,
/// con corrección de confusiones típicas del OCR según la posición.
library;

// Plantillas colombianas: L = letra, N = número
const plantillaCarro = 'LLLNNN'; // ABC123
const plantillaMoto = 'LLLNNL'; // ABC12D
final regexCarro = RegExp(r'^[A-Z]{3}[0-9]{3}$');
final regexMoto = RegExp(r'^[A-Z]{3}[0-9]{2}[A-Z]$');

// Confusiones típicas del OCR, corregidas según la posición
const _aLetra = {'0': 'O', '1': 'I', '5': 'S', '8': 'B', '2': 'Z', '6': 'G', '4': 'A'};
const _aNumero = {
  'O': '0', 'D': '0', 'Q': '0', 'I': '1', 'L': '1',
  'S': '5', 'B': '8', 'Z': '2', 'G': '6', 'A': '4',
};

/// Mayúsculas y solo caracteres alfanuméricos (quita espacios, guiones, puntos...).
String normalizar(String texto) => texto.toUpperCase().replaceAll(RegExp(r'[^A-Z0-9]'), '');

/// Corrige cada carácter según si en esa posición va letra (L) o número (N).
String corregirPorPlantilla(String texto, String plantilla) {
  if (texto.length != plantilla.length) return texto;
  final buffer = StringBuffer();
  for (var i = 0; i < texto.length; i++) {
    final c = texto[i];
    buffer.write(plantilla[i] == 'L' ? (_aLetra[c] ?? c) : (_aNumero[c] ?? c));
  }
  return buffer.toString();
}

/// Devuelve la placa normalizada si es colombiana válida (carro o moto), o null.
///
/// 1. Si el texto ya cumple uno de los formatos tal cual, se acepta sin tocarlo.
/// 2. Si no, se prueba la corrección de carro y luego la de moto.
String? validarColombia(String textoCrudo) {
  final texto = normalizar(textoCrudo);
  if (regexCarro.hasMatch(texto) || regexMoto.hasMatch(texto)) return texto;
  for (final (plantilla, regex) in [(plantillaCarro, regexCarro), (plantillaMoto, regexMoto)]) {
    final corregido = corregirPorPlantilla(texto, plantilla);
    if (regex.hasMatch(corregido)) return corregido;
  }
  return null;
}
