// Mismos casos que tests/test_tracker.py.
import 'package:flutter_test/flutter_test.dart';
import 'package:lector_placas/placas.dart';
import 'package:lector_placas/votacion.dart';

VotacionPlacas nueva({int votos = 3, double fusion = 3, double? mismaPlaca}) => VotacionPlacas(
    votosMinimos: votos, validar: validarColombia, segundosFusion: fusion, segundosFusionMismaPlaca: mismaPlaca);

void main() {
  test('firma y distancia', () {
    expect(firma('ABC123'), 'LLLNNN');
    expect(firma('ABC12D'), 'LLLNNL');
    expect(distancia('DEO81E', 'OEO81E'), 1);
    expect(distancia('ABC123', 'ABC12'), 6);
  });

  test('voto por caracter recupera placa sin lectura perfecta', () {
    final lecturas = ['IEO81E', 'DEO81E', 'OEO81E', 'DEO81E', 'NEO81E', 'DZO81E', 'DEQ81E', 'DEO61E', 'DED81E']
        .map((p) => (p, 0.5))
        .toList();
    expect(votarPorCaracter(lecturas), 'DEO81E');
  });

  test('voto ignora lecturas con otro patron', () {
    expect(votarPorCaracter([('NRZ267', 0.5), ('NRZ267', 0.5), ('NRZ26T', 0.9)]), 'NRZ267');
  });

  test('empate se decide por confianza', () {
    expect(votarPorCaracter([('ABC123', 0.9), ('ABC128', 0.2)]), 'ABC123');
  });

  test('no confirma antes de votos minimos', () {
    final v = nueva(votos: 3);
    expect(v.agregar(1, 'CTB816', 0.9, 0.0).$2, isFalse);
    expect(v.agregar(1, 'CTB816', 0.9, 0.1).$2, isFalse);
    expect(v.vehiculoDe(1)!.placaConfirmada, isNull);
    final (vehiculo, cambio) = v.agregar(1, 'CTB810', 0.5, 0.2);
    expect(cambio, isTrue);
    expect(vehiculo.placaConfirmada, 'CTB816');
  });

  test('no reporta cambio si la placa sigue igual', () {
    final v = nueva(votos: 2);
    v.agregar(1, 'CTB816', 0.9, 0.0);
    expect(v.agregar(1, 'CTB816', 0.9, 0.1).$2, isTrue);
    expect(v.agregar(1, 'CTB816', 0.9, 0.2).$2, isFalse);
  });

  test('vehiculos distintos no se fusionan', () {
    final v = nueva(votos: 2);
    for (var i = 0; i < 2; i++) {
      v.agregar(1, 'CTB816', 0.9, 0.0);
      v.agregar(2, 'HCV948', 0.9, 0.0);
    }
    expect(v.confirmados().map((x) => x.placaConfirmada), ['CTB816', 'HCV948']);
  });

  test('fusiona vehiculo que el seguimiento perdio', () {
    final v = nueva(votos: 2, fusion: 3);
    for (var i = 0; i < 3; i++) {
      v.agregar(10, 'DEO81E', 0.9, 36.0 + i);
    }
    v.agregar(11, 'OEO81E', 0.5, 39.5);
    final (vehiculo, _) = v.agregar(11, 'OEO81E', 0.5, 39.6);
    expect(vehiculo.trackId, 10);
    expect(v.confirmados().length, 1);
    expect(identical(v.vehiculoDe(11), v.vehiculoDe(10)), isTrue);
    expect(v.vehiculoDe(10)!.placaConfirmada, 'DEO81E');
    v.agregar(11, 'DEO81E', 0.9, 39.7);
    expect(v.vehiculoDe(10)!.lecturas.length, 6);
  });

  test('fusiona cuando la placa se corrige despues', () {
    final v = nueva(votos: 2, fusion: 10);
    for (var i = 0; i < 3; i++) {
      v.agregar(88, 'KAV637', 0.9, 26.0 + i);
    }
    for (var i = 0; i < 2; i++) {
      v.agregar(104, 'WAW450', 0.5, 37.0);
    }
    expect(v.confirmados().length, 2);
    for (var i = 0; i < 3; i++) {
      v.agregar(104, 'KAV637', 0.9, 38.0 + i);
    }
    expect(v.confirmados().map((x) => x.placaConfirmada), ['KAV637']);
    expect(identical(v.vehiculoDe(104), v.vehiculoDe(88)), isTrue);
    expect(v.vehiculoDe(88)!.primerSegundo, 26.0);
  });

  test('fusiona vehiculos que se solapan en el tiempo', () {
    final v = nueva(votos: 2, fusion: 10);
    for (var i = 0; i < 2; i++) {
      v.agregar(190, 'PUM731', 0.9, 113.7 + i);
      v.agregar(193, 'PUM731', 0.9, 114.0 + i);
    }
    expect(v.confirmados().length, 1);
    expect(v.confirmados().first.primerSegundo, 113.7);
  });

  test('placa identica se fusiona con ventana mas larga', () {
    final v = nueva(votos: 2, fusion: 10, mismaPlaca: 60);
    for (var i = 0; i < 2; i++) {
      v.agregar(93, 'OEQ81E', 0.9, 28.5);
    }
    for (var i = 0; i < 2; i++) {
      v.agregar(115, 'OEQ81E', 0.9, 40.1);
    }
    for (var i = 0; i < 2; i++) {
      v.agregar(120, 'OEQ81F', 0.9, 60.0);
    }
    expect(v.confirmados().map((x) => x.placaConfirmada), ['OEQ81E', 'OEQ81F']);
  });

  test('no fusiona si paso mucho tiempo', () {
    final v = nueva(votos: 2, fusion: 3);
    for (var i = 0; i < 2; i++) {
      v.agregar(10, 'DEO81E', 0.9, 10.0);
    }
    for (var i = 0; i < 2; i++) {
      v.agregar(11, 'OEO81E', 0.9, 60.0);
    }
    expect(v.confirmados().length, 2);
  });
}
