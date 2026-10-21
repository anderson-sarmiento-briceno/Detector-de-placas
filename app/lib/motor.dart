/// Motor de reconocimiento: detector + OCR con ONNX Runtime, en un isolate aparte
/// (hilo en segundo plano) para que la cámara y la pantalla no se congelen.
///
/// Recibe el frame de la cámara en YUV420 (como lo entrega Android) y:
/// 1. Lo convierte a RGB "derecho" (girado según la orientación del sensor) y en
///    formato carta 640x640 (letterbox, relleno gris 114) para el detector.
/// 2. Corre el detector (detector.onnx, con NMS incluido): cajas en coordenadas del frame.
/// 3. Recorta cada placa (con 10 % de margen, como en el PC), la escala a 128x64 y
///    corre el OCR (ocr.onnx) con todas las placas del frame en un solo lote.
library;

import 'dart:async';
import 'dart:isolate';
import 'dart:math' as math;
import 'dart:typed_data';

import 'package:onnxruntime/onnxruntime.dart';

const tamDetector = 640;
const anchoOcr = 128, altoOcr = 64;
const alfabetoOcr = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ_';
const caracterRelleno = '_';

// Mismos valores que config.yaml del PC
const confianzaMinimaDeteccion = 0.4;
const altoMinimoCajaPx = 15.0;
const margenRecorte = 0.1;

/// Un frame de la cámara listo para enviar al isolate.
class FrameYuv {
  FrameYuv({
    required this.ancho,
    required this.alto,
    required this.rotacion,
    required this.y,
    required this.u,
    required this.v,
    required this.filaY,
    required this.filaUv,
    required this.pasoUv,
  });

  final int ancho, alto; // tal como lo entrega el sensor (normalmente horizontal)
  final int rotacion; // grados para ponerlo derecho: 0, 90, 180, 270
  final TransferableTypedData y, u, v;
  final int filaY, filaUv, pasoUv; // bytes por fila y entre píxeles U/V
}

/// Una placa detectada y leída, en coordenadas del frame derecho.
class Lectura {
  const Lectura(this.x1, this.y1, this.x2, this.y2, this.confDeteccion, this.texto, this.confOcr);
  final double x1, y1, x2, y2, confDeteccion;
  final String texto;
  final double confOcr;
}

class ResultadoFrame {
  const ResultadoFrame(this.anchoDerecho, this.altoDerecho, this.lecturas, this.msDetector, this.msOcr);
  final int anchoDerecho, altoDerecho;
  final List<Lectura> lecturas;
  final int msDetector, msOcr;
}

/// Acceso a un frame YUV como si ya estuviera girado ("derecho").
class ImagenYuv {
  ImagenYuv(this.y, this.u, this.v,
      {required this.ancho,
      required this.alto,
      required this.rotacion,
      required this.filaY,
      required this.filaUv,
      required this.pasoUv});

  ImagenYuv.desdeFrame(FrameYuv f)
      : this(f.y.materialize().asUint8List(), f.u.materialize().asUint8List(), f.v.materialize().asUint8List(),
            ancho: f.ancho,
            alto: f.alto,
            rotacion: f.rotacion,
            filaY: f.filaY,
            filaUv: f.filaUv,
            pasoUv: f.pasoUv);

  final Uint8List y, u, v;
  final int ancho, alto, rotacion, filaY, filaUv, pasoUv;

  int get anchoDerecho => rotacion % 180 == 0 ? ancho : alto;
  int get altoDerecho => rotacion % 180 == 0 ? alto : ancho;

  /// Escribe en [rgb] (desde [i]) el color del píxel (xd, yd) del frame derecho.
  void pixel(int xd, int yd, List<num> rgb, int i, {bool normalizar = false, int salto = 1}) {
    int xs, ys;
    switch (rotacion) {
      case 90:
        xs = yd;
        ys = alto - 1 - xd;
      case 180:
        xs = ancho - 1 - xd;
        ys = alto - 1 - yd;
      case 270:
        xs = ancho - 1 - yd;
        ys = xd;
      default:
        xs = xd;
        ys = yd;
    }
    final yy = y[ys * filaY + xs];
    final iuv = (ys >> 1) * filaUv + (xs >> 1) * pasoUv;
    final uu = u[iuv] - 128, vv = v[iuv] - 128;
    var r = (yy + 1.402 * vv).round(), g = (yy - 0.344136 * uu - 0.714136 * vv).round(), b = (yy + 1.772 * uu).round();
    r = r < 0 ? 0 : (r > 255 ? 255 : r);
    g = g < 0 ? 0 : (g > 255 ? 255 : g);
    b = b < 0 ? 0 : (b > 255 ? 255 : b);
    if (normalizar) {
      rgb[i] = r / 255.0;
      rgb[i + salto] = g / 255.0;
      rgb[i + 2 * salto] = b / 255.0;
    } else {
      rgb[i] = r;
      rgb[i + salto] = g;
      rgb[i + 2 * salto] = b;
    }
  }
}

class _Motor {
  _Motor(Uint8List bytesDetector, Uint8List bytesOcr) {
    OrtEnv.instance.init();
    final opciones = OrtSessionOptions()
      ..setIntraOpNumThreads(4)
      ..setSessionGraphOptimizationLevel(GraphOptimizationLevel.ortEnableAll);
    detector = OrtSession.fromBuffer(bytesDetector, opciones);
    ocr = OrtSession.fromBuffer(bytesOcr, opciones);
  }

  late final OrtSession detector, ocr;
  final _entradaDetector = Float32List(3 * tamDetector * tamDetector);

  ResultadoFrame procesar(FrameYuv frame) {
    final img = ImagenYuv.desdeFrame(frame);
    final reloj = Stopwatch()..start();
    final cajas = _detectar(img);
    final msDetector = reloj.elapsedMilliseconds;
    final lecturas = _leer(img, cajas);
    return ResultadoFrame(img.anchoDerecho, img.altoDerecho, lecturas, msDetector,
        reloj.elapsedMilliseconds - msDetector);
  }

  /// Letterbox 640x640 (como Ultralytics), detector, y cajas en coordenadas del frame derecho.
  List<List<double>> _detectar(ImagenYuv img) {
    final w = img.anchoDerecho, h = img.altoDerecho;
    final escala = tamDetector / math.max(w, h);
    final nuevoW = (w * escala).round(), nuevoH = (h * escala).round();
    final padX = (tamDetector - nuevoW) ~/ 2, padY = (tamDetector - nuevoH) ~/ 2;
    final plano = tamDetector * tamDetector;
    _entradaDetector.fillRange(0, _entradaDetector.length, 114 / 255.0);
    for (var oy = 0; oy < nuevoH; oy++) {
      final yd = math.min(h - 1, (oy / escala).floor());
      for (var ox = 0; ox < nuevoW; ox++) {
        final xd = math.min(w - 1, (ox / escala).floor());
        img.pixel(xd, yd, _entradaDetector, (oy + padY) * tamDetector + ox + padX, normalizar: true, salto: plano);
      }
    }
    final entrada = OrtValueTensor.createTensorWithDataList(_entradaDetector, [1, 3, tamDetector, tamDetector]);
    final opciones = OrtRunOptions();
    final salidas = detector.run(opciones, {'images': entrada});
    final filas = (salidas[0]!.value as List)[0] as List; // [300][x1, y1, x2, y2, conf, clase]
    entrada.release();
    opciones.release();
    for (final s in salidas) {
      s?.release();
    }
    final cajas = <List<double>>[];
    for (final f in filas) {
      final conf = (f[4] as num).toDouble();
      if (conf < confianzaMinimaDeteccion) continue;
      final x1 = ((f[0] as num) - padX) / escala, y1 = ((f[1] as num) - padY) / escala;
      final x2 = ((f[2] as num) - padX) / escala, y2 = ((f[3] as num) - padY) / escala;
      if (y2 - y1 < altoMinimoCajaPx) continue; // muy pequeñas: no se pueden leer
      cajas.add([x1, y1, x2, y2, conf]);
    }
    return cajas;
  }

  /// Recorta todas las placas, las escala a 128x64 RGB y las lee en un solo lote.
  List<Lectura> _leer(ImagenYuv img, List<List<double>> cajas) {
    if (cajas.isEmpty) return const [];
    final w = img.anchoDerecho, h = img.altoDerecho;
    final porPlaca = anchoOcr * altoOcr * 3;
    final entrada = Uint8List(cajas.length * porPlaca);
    for (var k = 0; k < cajas.length; k++) {
      final c = cajas[k];
      final mx = (c[2] - c[0]) * margenRecorte, my = (c[3] - c[1]) * margenRecorte;
      final x1 = math.max(0.0, c[0] - mx), y1 = math.max(0.0, c[1] - my);
      final x2 = math.min(w.toDouble(), c[2] + mx), y2 = math.min(h.toDouble(), c[3] + my);
      final sx = (x2 - x1) / anchoOcr, sy = (y2 - y1) / altoOcr;
      for (var oy = 0; oy < altoOcr; oy++) {
        final yd = math.min(h - 1, (y1 + (oy + 0.5) * sy).floor());
        for (var ox = 0; ox < anchoOcr; ox++) {
          final xd = math.min(w - 1, (x1 + (ox + 0.5) * sx).floor());
          img.pixel(xd, yd, entrada, k * porPlaca + (oy * anchoOcr + ox) * 3);
        }
      }
    }
    final tensor = OrtValueTensor.createTensorWithDataList(entrada, [cajas.length, altoOcr, anchoOcr, 3]);
    final opciones = OrtRunOptions();
    final salidas = ocr.run(opciones, {'input': tensor});
    final probs = salidas[0]!.value as List; // [n][10][37]
    tensor.release();
    opciones.release();
    for (final s in salidas) {
      s?.release();
    }
    final lecturas = <Lectura>[];
    for (var k = 0; k < cajas.length; k++) {
      final texto = StringBuffer();
      var confMin = 1.0;
      for (final posicion in probs[k] as List) {
        final p = (posicion as List).cast<num>();
        var mejor = 0;
        for (var i = 1; i < p.length; i++) {
          if (p[i] > p[mejor]) mejor = i;
        }
        final ch = alfabetoOcr[mejor];
        if (ch == caracterRelleno) continue;
        texto.write(ch);
        confMin = math.min(confMin, p[mejor].toDouble());
      }
      final c = cajas[k];
      lecturas.add(Lectura(c[0], c[1], c[2], c[3], c[4], texto.toString(), texto.isEmpty ? 0 : confMin));
    }
    return lecturas;
  }
}

/// Punto de entrada del isolate: [SendPort de respuesta, bytes detector, bytes OCR].
void _principal(List<Object> args) {
  final respuesta = args[0] as SendPort;
  final motor = _Motor(args[1] as Uint8List, args[2] as Uint8List);
  final entrada = ReceivePort();
  respuesta.send(entrada.sendPort);
  entrada.listen((mensaje) {
    try {
      respuesta.send(motor.procesar(mensaje as FrameYuv));
    } catch (e) {
      respuesta.send('error: $e');
    }
  });
}

/// Maneja el isolate desde la pantalla: un frame a la vez (si está ocupado, se descarta).
class MotorPlacas {
  SendPort? _envio;
  final _respuestas = ReceivePort();
  void Function(ResultadoFrame)? _alResultado;
  void Function(String)? _alError;
  bool ocupado = false;

  Future<void> iniciar(Uint8List bytesDetector, Uint8List bytesOcr,
      {required void Function(ResultadoFrame) alResultado, required void Function(String) alError}) async {
    _alResultado = alResultado;
    _alError = alError;
    final listo = Completer<void>();
    // Un ReceivePort solo se puede escuchar una vez: el primer mensaje es el SendPort del isolate
    _respuestas.listen((m) {
      if (m is SendPort) {
        _envio = m;
        listo.complete();
        return;
      }
      ocupado = false;
      if (m is ResultadoFrame) {
        _alResultado?.call(m);
      } else {
        _alError?.call(m.toString());
      }
    });
    await Isolate.spawn(_principal, [_respuestas.sendPort, bytesDetector, bytesOcr]);
    await listo.future;
  }

  /// Envía un frame si el motor está libre. Devuelve false si se descartó.
  bool enviar(FrameYuv frame) {
    if (ocupado || _envio == null) return false;
    ocupado = true;
    _envio!.send(frame);
    return true;
  }
}
