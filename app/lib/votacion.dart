/// Votación temporal: junta las lecturas de un mismo vehículo y confirma una sola placa.
///
/// Traducción de src/tracker.py. El OCR se equivoca en 1-2 caracteres de forma
/// distinta en cada frame; se vota carácter por carácter entre las lecturas del
/// mismo vehículo. Si el seguimiento pierde un vehículo y le da un ID nuevo, se
/// fusiona con el anterior cuando su placa es casi igual y apareció poco después.
library;

const maxDiferenciasFusion = 1;

/// Patrón letra/número: 'ABC123' → 'LLLNNN', 'ABC12D' → 'LLLNNL'.
String firma(String placa) =>
    placa.split('').map((c) => RegExp(r'[0-9]').hasMatch(c) ? 'N' : 'L').join();

/// Cantidad de caracteres distintos (placas de distinto largo: el largo mayor).
int distancia(String a, String b) {
  if (a.length != b.length) return a.length > b.length ? a.length : b.length;
  var n = 0;
  for (var i = 0; i < a.length; i++) {
    if (a[i] != b[i]) n++;
  }
  return n;
}

typedef Lectura = (String placa, double confianza);

/// Placa con el carácter más votado en cada posición (empates: suma de confianzas),
/// usando solo las lecturas con el patrón más común (para no mezclar carro y moto).
String votarPorCaracter(List<Lectura> lecturas) {
  final conteo = <String, int>{};
  for (final (p, _) in lecturas) {
    conteo[firma(p)] = (conteo[firma(p)] ?? 0) + 1;
  }
  // Con empate gana el patrón que apareció primero (igual que Counter.most_common)
  var patron = conteo.keys.first;
  for (final k in conteo.keys) {
    if (conteo[k]! > conteo[patron]!) patron = k;
  }
  final grupo = lecturas.where((l) => firma(l.$1) == patron).toList();
  final resultado = StringBuffer();
  for (var i = 0; i < patron.length; i++) {
    final votos = <String, List<double>>{};
    for (final (placa, conf) in grupo) {
      votos.putIfAbsent(placa[i], () => []).add(conf);
    }
    String? mejor;
    for (final ch in votos.keys) {
      if (mejor == null) {
        mejor = ch;
        continue;
      }
      final a = votos[ch]!, b = votos[mejor]!;
      final sumaA = a.fold(0.0, (s, x) => s + x), sumaB = b.fold(0.0, (s, x) => s + x);
      if (a.length > b.length || (a.length == b.length && sumaA > sumaB)) mejor = ch;
    }
    resultado.write(mejor);
  }
  return resultado.toString();
}

class Vehiculo {
  Vehiculo(this.trackId, this.primerSegundo, this.ultimoSegundo);

  final int trackId;
  double primerSegundo;
  double ultimoSegundo;
  final List<Lectura> lecturas = [];
  String? placaConfirmada;
}

/// Segundos entre los intervalos en que se vio cada vehículo (≤ 0 si se solapan).
double separacionSegundos(Vehiculo a, Vehiculo b) {
  final inicio = a.primerSegundo > b.primerSegundo ? a.primerSegundo : b.primerSegundo;
  final fin = a.ultimoSegundo < b.ultimoSegundo ? a.ultimoSegundo : b.ultimoSegundo;
  return inicio - fin;
}

class VotacionPlacas {
  VotacionPlacas({
    required this.votosMinimos,
    required this.validar,
    required this.segundosFusion,
    double? segundosFusionMismaPlaca,
  }) : segundosFusionMismaPlaca =
            (segundosFusionMismaPlaca ?? 0) > segundosFusion ? segundosFusionMismaPlaca! : segundosFusion;

  final int votosMinimos;
  final String? Function(String) validar;
  final double segundosFusion;
  final double segundosFusionMismaPlaca;
  final Map<int, Vehiculo> vehiculos = {};
  final Map<int, int> alias = {}; // track_id nuevo → track_id del vehículo con el que se fusionó

  Vehiculo? vehiculoDe(int? trackId) {
    if (trackId == null) return null;
    return vehiculos[alias[trackId] ?? trackId];
  }

  /// Agrega una lectura válida. Devuelve (vehículo, si su placa confirmada cambió).
  (Vehiculo, bool) agregar(int trackId, String placa, double confianza, double segundo) {
    var v = vehiculoDe(trackId);
    if (v == null) {
      v = Vehiculo(trackId, segundo, segundo);
      vehiculos[trackId] = v;
    }
    v.lecturas.add((placa, confianza));
    v.ultimoSegundo = segundo;
    if (v.lecturas.length < votosMinimos) return (v, false);
    if (!_revotar(v)) return (v, false);
    final anterior = _buscarParaFusion(v);
    if (anterior != null) {
      _fusionar(v, anterior);
      return (anterior, true);
    }
    return (v, true);
  }

  bool _revotar(Vehiculo v) {
    final votada = validar(votarPorCaracter(v.lecturas));
    if (votada != null && votada != v.placaConfirmada) {
      v.placaConfirmada = votada;
      return true;
    }
    return false;
  }

  Vehiculo? _buscarParaFusion(Vehiculo nuevo) {
    Vehiculo? mejor;
    for (final v in vehiculos.values) {
      if (identical(v, nuevo) || v.placaConfirmada == null) continue;
      final diferencias = distancia(v.placaConfirmada!, nuevo.placaConfirmada!);
      final limite = diferencias == 0 ? segundosFusionMismaPlaca : segundosFusion;
      if (diferencias <= maxDiferenciasFusion && separacionSegundos(v, nuevo) <= limite) {
        if (mejor == null || v.ultimoSegundo > mejor.ultimoSegundo) mejor = v;
      }
    }
    return mejor;
  }

  void _fusionar(Vehiculo nuevo, Vehiculo anterior) {
    anterior.lecturas.addAll(nuevo.lecturas);
    if (nuevo.primerSegundo < anterior.primerSegundo) anterior.primerSegundo = nuevo.primerSegundo;
    if (nuevo.ultimoSegundo > anterior.ultimoSegundo) anterior.ultimoSegundo = nuevo.ultimoSegundo;
    vehiculos.remove(nuevo.trackId);
    alias[nuevo.trackId] = anterior.trackId;
    for (final viejo in alias.keys.toList()) {
      if (alias[viejo] == nuevo.trackId) alias[viejo] = anterior.trackId;
    }
    _revotar(anterior);
  }

  List<Vehiculo> confirmados() =>
      vehiculos.values.where((v) => v.placaConfirmada != null).toList()
        ..sort((a, b) => a.primerSegundo.compareTo(b.primerSegundo));
}
