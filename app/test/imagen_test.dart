// Prueba del giro del frame de la cámara y de la conversión YUV → RGB.
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:lector_placas/motor.dart';

/// Sensor de 4x2 píxeles (horizontal), cada píxel con un brillo distinto y sin color.
ImagenYuv sensor4x2(int rotacion) {
  final y = Uint8List.fromList([10, 20, 30, 40, 50, 60, 70, 80]); // fila 0: 10..40, fila 1: 50..80
  final gris = Uint8List.fromList([128, 128]); // U y V neutros: RGB = Y
  return ImagenYuv(y, gris, gris, ancho: 4, alto: 2, rotacion: rotacion, filaY: 4, filaUv: 2, pasoUv: 1);
}

int brillo(ImagenYuv img, int x, int y) {
  final rgb = List<num>.filled(3, 0);
  img.pixel(x, y, rgb, 0);
  return rgb[0].toInt();
}

void main() {
  test('sin rotacion', () {
    final img = sensor4x2(0);
    expect([img.anchoDerecho, img.altoDerecho], [4, 2]);
    expect(brillo(img, 0, 0), 10);
    expect(brillo(img, 3, 1), 80);
  });

  test('rotacion 90 (camara trasera tipica): se gira en sentido horario', () {
    final img = sensor4x2(90);
    expect([img.anchoDerecho, img.altoDerecho], [2, 4]); // queda vertical
    // Arriba a la izquierda queda la esquina inferior izquierda del sensor
    expect(brillo(img, 0, 0), 50);
    expect(brillo(img, 1, 0), 10);
    expect(brillo(img, 0, 3), 80);
    expect(brillo(img, 1, 3), 40);
  });

  test('rotacion 270', () {
    final img = sensor4x2(270);
    expect(brillo(img, 0, 0), 40);
    expect(brillo(img, 1, 3), 50);
  });

  test('yuv a rgb: rojo', () {
    final img = ImagenYuv(Uint8List.fromList([81]), Uint8List.fromList([90]), Uint8List.fromList([240]),
        ancho: 1, alto: 1, rotacion: 0, filaY: 1, filaUv: 1, pasoUv: 1);
    final rgb = List<num>.filled(3, 0);
    img.pixel(0, 0, rgb, 0);
    expect(rgb[0], greaterThan(220));
    expect(rgb[1], lessThan(30));
    expect(rgb[2], lessThan(30));
  });
}
