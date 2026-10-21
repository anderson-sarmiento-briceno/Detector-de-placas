/// Lector de placas colombianas con la cámara del celular.
///
/// Igual que el programa del PC (src/main.py): detector → seguimiento → OCR →
/// validación colombiana → votación. Las placas se dibujan sobre la cámara:
/// amarillo con "?" mientras se leen, verde cuando la votación las confirma.
library;

import 'dart:async';
import 'dart:isolate';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:wakelock_plus/wakelock_plus.dart';

import 'motor.dart';
import 'placas.dart';
import 'seguimiento.dart';
import 'votacion.dart';

// Mismos valores que config.yaml del PC
const confianzaMinimaOcr = 0.5;
const votosMinimos = 3;
const segundosFusion = 10.0;
const segundosFusionMismaPlaca = 60.0;

const verde = Color(0xFF00E000);
const amarillo = Color(0xFFFFDC00);

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]);
  runApp(const MaterialApp(debugShowCheckedModeBanner: false, home: PantallaLector()));
}

/// Lo que se dibuja de cada placa en el frame actual.
class PlacaEnPantalla {
  const PlacaEnPantalla(this.caja, this.etiqueta, this.confirmada);
  final Caja caja;
  final String etiqueta;
  final bool confirmada;
}

class PantallaLector extends StatefulWidget {
  const PantallaLector({super.key});

  @override
  State<PantallaLector> createState() => _EstadoLector();
}

class _EstadoLector extends State<PantallaLector> {
  CameraController? _camara;
  final _motor = MotorPlacas();
  final _seguimiento = Seguimiento();
  final _votacion = VotacionPlacas(
      votosMinimos: votosMinimos,
      validar: validarColombia,
      segundosFusion: segundosFusion,
      segundosFusionMismaPlaca: segundosFusionMismaPlaca);
  final _reloj = Stopwatch()..start();

  String _estado = 'Cargando modelos...';
  List<PlacaEnPantalla> _placas = [];
  Size _tamFrame = const Size(1080, 1920);
  final List<DateTime> _tiemposResultado = [];
  int _msDetector = 0, _msOcr = 0;

  @override
  void initState() {
    super.initState();
    WakelockPlus.enable(); // que la pantalla no se apague mientras lee
    _iniciar();
  }

  Future<void> _iniciar() async {
    try {
      final detector = (await rootBundle.load('assets/models/detector.onnx')).buffer.asUint8List();
      final ocr = (await rootBundle.load('assets/models/ocr.onnx')).buffer.asUint8List();
      await _motor.iniciar(detector, ocr, alResultado: _alResultado, alError: (e) => setState(() => _estado = e));

      final camaras = await availableCameras();
      final trasera = camaras.firstWhere((c) => c.lensDirection == CameraLensDirection.back,
          orElse: () => camaras.first);
      final camara = CameraController(trasera, ResolutionPreset.veryHigh,
          enableAudio: false, imageFormatGroup: ImageFormatGroup.yuv420);
      await camara.initialize();
      await camara.startImageStream((imagen) => _alFrame(imagen, trasera.sensorOrientation));
      setState(() {
        _camara = camara;
        _estado = '';
      });
    } catch (e) {
      setState(() => _estado = 'Error al iniciar: $e');
    }
  }

  void _alFrame(CameraImage imagen, int rotacion) {
    if (_motor.ocupado || imagen.planes.length < 3) return; // se descarta: el motor sigue con el anterior
    final p = imagen.planes;
    _motor.enviar(FrameYuv(
      ancho: imagen.width,
      alto: imagen.height,
      rotacion: rotacion,
      y: TransferableTypedData.fromList([p[0].bytes]),
      u: TransferableTypedData.fromList([p[1].bytes]),
      v: TransferableTypedData.fromList([p[2].bytes]),
      filaY: p[0].bytesPerRow,
      filaUv: p[1].bytesPerRow,
      pasoUv: p[1].bytesPerPixel ?? 1,
    ));
  }

  void _alResultado(ResultadoFrame r) {
    final segundo = _reloj.elapsedMilliseconds / 1000.0;
    final cajas = [for (final l in r.lecturas) Caja(l.x1, l.y1, l.x2, l.y2)];
    final ids = _seguimiento.actualizar(cajas);
    final placas = <PlacaEnPantalla>[];
    for (var i = 0; i < r.lecturas.length; i++) {
      final l = r.lecturas[i];
      // Lecturas dudosas (placa lejana o algo que no es placa) no votan
      final placa = l.confOcr >= confianzaMinimaOcr ? validarColombia(l.texto) : null;
      if (placa != null) _votacion.agregar(ids[i], placa, l.confOcr, segundo);
      final vehiculo = _votacion.vehiculoDe(ids[i]);
      final confirmada = vehiculo?.placaConfirmada;
      placas.add(PlacaEnPantalla(
          cajas[i], confirmada ?? '? ${placa ?? l.texto}', confirmada != null));
    }
    final ahora = DateTime.now();
    _tiemposResultado
      ..add(ahora)
      ..removeWhere((t) => ahora.difference(t).inMilliseconds > 2000);
    setState(() {
      _placas = placas;
      _tamFrame = Size(r.anchoDerecho.toDouble(), r.altoDerecho.toDouble());
      _msDetector = r.msDetector;
      _msOcr = r.msOcr;
    });
  }

  @override
  void dispose() {
    WakelockPlus.disable();
    _camara?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final camara = _camara;
    final confirmadas = _votacion.confirmados().reversed.toList(); // la más reciente primero
    final fps = _tiemposResultado.length / 2.0;
    return Scaffold(
      backgroundColor: Colors.black,
      body: SafeArea(
        child: Column(children: [
          Padding(
            padding: const EdgeInsets.all(8),
            child: Text(
              camara == null
                  ? _estado
                  : '${fps.toStringAsFixed(1)} FPS   detector ${_msDetector}ms   OCR ${_msOcr}ms'
                      '${_estado.isEmpty ? '' : '\n$_estado'}',
              style: const TextStyle(color: Colors.white, fontSize: 14),
            ),
          ),
          Expanded(
            child: Center(
              child: camara == null
                  ? const CircularProgressIndicator()
                  : AspectRatio(
                      aspectRatio: _tamFrame.width / _tamFrame.height,
                      child: Stack(fit: StackFit.expand, children: [
                        CameraPreview(camara),
                        CustomPaint(painter: _DibujoPlacas(_placas, _tamFrame)),
                      ]),
                    ),
            ),
          ),
          Container(
            height: 92,
            width: double.infinity,
            color: const Color(0xFF111111),
            padding: const EdgeInsets.all(8),
            child: confirmadas.isEmpty
                ? const Center(
                    child: Text('Apunta la cámara a las placas', style: TextStyle(color: Colors.white54)))
                : ListView(scrollDirection: Axis.horizontal, children: [
                    for (final v in confirmadas)
                      Container(
                        margin: const EdgeInsets.only(right: 8),
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                        decoration: BoxDecoration(color: amarillo, borderRadius: BorderRadius.circular(6)),
                        child: Center(
                          child: Text(v.placaConfirmada!,
                              style: const TextStyle(
                                  fontSize: 26, fontWeight: FontWeight.bold, letterSpacing: 2, color: Colors.black)),
                        ),
                      ),
                  ]),
          ),
        ]),
      ),
    );
  }
}

/// Dibuja la caja de cada placa y su etiqueta encima, sobre un fondo de color.
class _DibujoPlacas extends CustomPainter {
  _DibujoPlacas(this.placas, this.tamFrame);
  final List<PlacaEnPantalla> placas;
  final Size tamFrame;

  @override
  void paint(Canvas canvas, Size size) {
    final escala = size.width / tamFrame.width;
    for (final p in placas) {
      final color = p.confirmada ? verde : amarillo;
      final rect = Rect.fromLTRB(p.caja.x1 * escala, p.caja.y1 * escala, p.caja.x2 * escala, p.caja.y2 * escala);
      canvas.drawRect(
          rect,
          Paint()
            ..color = color
            ..style = PaintingStyle.stroke
            ..strokeWidth = 3);
      final texto = TextPainter(
        text: TextSpan(
            text: p.etiqueta,
            style: const TextStyle(color: Colors.black, fontSize: 18, fontWeight: FontWeight.bold)),
        textDirection: TextDirection.ltr,
      )..layout();
      final fondo = Rect.fromLTWH(rect.left, rect.top - texto.height - 6, texto.width + 10, texto.height + 4);
      canvas.drawRect(fondo, Paint()..color = color);
      texto.paint(canvas, Offset(fondo.left + 5, fondo.top + 2));
    }
  }

  @override
  bool shouldRepaint(_DibujoPlacas old) => old.placas != placas || old.tamFrame != tamFrame;
}
