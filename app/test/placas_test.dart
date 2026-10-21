// Mismos casos que tests/test_plate_utils.py (modo colombia).
import 'package:flutter_test/flutter_test.dart';
import 'package:lector_placas/placas.dart';

void main() {
  test('normalizar quita guiones y espacios', () {
    expect(normalizar(' abc-123 '), 'ABC123');
    expect(normalizar('AB.C 1·23'), 'ABC123');
  });

  test('carro', () {
    const casos = {
      'ABC123': 'ABC123',
      'abc-123': 'ABC123',
      'A8C1Z3': 'ABC123', // 8→B en letra, Z→2 en número
      '0BC12O': 'OBC120', // 0→O en letra, O→0 en número
      '5GA1B4': 'SGA184',
    };
    casos.forEach((crudo, esperado) => expect(validarColombia(crudo), esperado, reason: crudo));
  });

  test('moto', () {
    const casos = {
      'ABC12D': 'ABC12D',
      'abc 12d': 'ABC12D',
      'WRG-22H': 'WRG22H',
      'W8G2ZH': 'WBG22H',
      'ABCI2K': 'ABC12K', // I→1 en número; K no es número → plantilla moto
    };
    casos.forEach((crudo, esperado) => expect(validarColombia(crudo), esperado, reason: crudo));
  });

  test('invalidas', () {
    for (final crudo in ['ABC12', 'ABC1234', '1234AB', '', 'BOGOTA', 'VBC75', '12ABCD']) {
      expect(validarColombia(crudo), isNull, reason: crudo);
    }
  });

  test('corregir ignora largo distinto de 6', () {
    expect(corregirPorPlantilla('A8C12', plantillaCarro), 'A8C12');
  });
}
