/// Seguimiento sencillo de placas entre frames (reemplaza al ByteTrack de YOLO en el PC).
///
/// Cada caja nueva se asocia a la placa del frame anterior con la que más se solapa
/// (o, si no se solapan, la más cercana en relación con su tamaño: con la cámara en
/// movimiento una placa pequeña puede saltar más que su propio ancho). Las placas que
/// no aparecen en [maxFramesPerdida] frames procesados se olvidan.
library;

import 'dart:math' as math;

class Caja {
  const Caja(this.x1, this.y1, this.x2, this.y2);
  final double x1, y1, x2, y2;

  double get ancho => x2 - x1;
  double get alto => y2 - y1;
  double get cx => (x1 + x2) / 2;
  double get cy => (y1 + y2) / 2;

  double iou(Caja o) {
    final ix = math.max(0.0, math.min(x2, o.x2) - math.max(x1, o.x1));
    final iy = math.max(0.0, math.min(y2, o.y2) - math.max(y1, o.y1));
    final inter = ix * iy;
    final union = ancho * alto + o.ancho * o.alto - inter;
    return union > 0 ? inter / union : 0;
  }

  /// Distancia entre centros medida en "anchos de caja" (0 = mismo centro).
  double distanciaRelativa(Caja o) {
    final d = math.sqrt(math.pow(cx - o.cx, 2) + math.pow(cy - o.cy, 2));
    return d / math.max(1.0, math.max(ancho, o.ancho));
  }
}

class _Pista {
  _Pista(this.id, this.caja);
  final int id;
  Caja caja;
  int perdidos = 0;
}

class Seguimiento {
  Seguimiento({this.iouMinimo = 0.2, this.distanciaMaxima = 1.5, this.maxFramesPerdida = 10});

  final double iouMinimo;
  final double distanciaMaxima;
  final int maxFramesPerdida;
  final List<_Pista> _pistas = [];
  int _siguienteId = 1;

  void reiniciar() {
    _pistas.clear();
  }

  /// Devuelve el id de seguimiento de cada caja, en el mismo orden.
  List<int> actualizar(List<Caja> cajas) {
    // Pares (puntaje, caja, pista), mejor primero: asociación codiciosa
    final pares = <(double, int, int)>[];
    for (var i = 0; i < cajas.length; i++) {
      for (var j = 0; j < _pistas.length; j++) {
        final iou = cajas[i].iou(_pistas[j].caja);
        final dist = cajas[i].distanciaRelativa(_pistas[j].caja);
        if (iou >= iouMinimo) {
          pares.add((1 + iou, i, j));
        } else if (dist <= distanciaMaxima) {
          pares.add((1 - dist / distanciaMaxima, i, j));
        }
      }
    }
    pares.sort((a, b) => b.$1.compareTo(a.$1));
    final ids = List<int>.filled(cajas.length, -1);
    final pistaUsada = List<bool>.filled(_pistas.length, false);
    for (final (_, i, j) in pares) {
      if (ids[i] != -1 || pistaUsada[j]) continue;
      ids[i] = _pistas[j].id;
      _pistas[j]
        ..caja = cajas[i]
        ..perdidos = 0;
      pistaUsada[j] = true;
    }
    for (var j = 0; j < _pistas.length; j++) {
      if (!pistaUsada[j]) _pistas[j].perdidos++;
    }
    _pistas.removeWhere((p) => p.perdidos > maxFramesPerdida);
    for (var i = 0; i < cajas.length; i++) {
      if (ids[i] == -1) {
        final p = _Pista(_siguienteId++, cajas[i]);
        _pistas.add(p);
        ids[i] = p.id;
      }
    }
    return ids;
  }
}
