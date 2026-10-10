"""Votación temporal: junta las lecturas de un mismo vehículo y confirma una sola placa.

El OCR se equivoca en 1-2 caracteres de forma distinta en cada frame
(IEO81E, DEO81E, OEO81E...). En vez de exigir que el texto completo se repita,
se vota **carácter por carácter** entre todas las lecturas del mismo vehículo
(mismo `track_id` de YOLO).

Si el seguimiento pierde un vehículo un momento y le asigna un ID nuevo, se
**fusiona** con el anterior cuando su placa difiere en máximo 1 carácter y
apareció pocos segundos después.
"""
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

MAX_DIFERENCIAS_FUSION = 1


def firma(placa: str) -> str:
    """Patrón letra/número: 'ABC123' → 'LLLNNN', 'ABC12D' → 'LLLNNL'."""
    return "".join("N" if c.isdigit() else "L" for c in placa)


def distancia(a: str, b: str) -> int:
    """Cantidad de caracteres distintos (placas de distinto largo: el largo mayor)."""
    if len(a) != len(b):
        return max(len(a), len(b))
    return sum(x != y for x, y in zip(a, b))


def votar_por_caracter(lecturas: list[tuple[str, float]]) -> str:
    """Devuelve la placa con el carácter más votado en cada posición.

    1. Se usa solo el grupo de lecturas con el patrón más común (mismo largo y
       misma posición de letras/números), para no mezclar p. ej. carro y moto.
    2. En cada posición gana el carácter con más votos; los empates se deciden
       por la suma de confianzas del OCR.
    """
    patron, _ = Counter(firma(p) for p, _ in lecturas).most_common(1)[0]
    grupo = [(p, c) for p, c in lecturas if firma(p) == patron]
    resultado = []
    for i in range(len(patron)):
        votos: dict[str, list[float]] = defaultdict(list)
        for placa, conf in grupo:
            votos[placa[i]].append(conf)
        resultado.append(max(votos, key=lambda ch: (len(votos[ch]), sum(votos[ch]))))
    return "".join(resultado)


@dataclass
class Vehiculo:
    track_id: int
    primer_frame: int
    primer_segundo: float
    ultimo_segundo: float
    lecturas: list[tuple[str, float]] = field(default_factory=list)
    placa_confirmada: str | None = None

    @property
    def confianza(self) -> float:
        return sum(c for _, c in self.lecturas) / len(self.lecturas)


class VotacionPlacas:
    def __init__(self, votos_minimos: int, validar: Callable[[str], str | None],
                 segundos_fusion: float) -> None:
        """`validar` vuelve a comprobar el formato del texto votado (p. ej. validar_placa)."""
        self.votos_minimos = votos_minimos
        self.validar = validar
        self.segundos_fusion = segundos_fusion
        self.vehiculos: dict[int, Vehiculo] = {}
        self.alias: dict[int, int] = {}   # track_id nuevo → track_id del vehículo con el que se fusionó

    def vehiculo_de(self, track_id: int | None) -> Vehiculo | None:
        if track_id is None:
            return None
        return self.vehiculos.get(self.alias.get(track_id, track_id))

    def agregar(self, track_id: int, placa: str, confianza: float,
                frame: int, segundo: float) -> tuple[Vehiculo, bool]:
        """Agrega una lectura válida. Devuelve (vehículo, si su placa confirmada cambió)."""
        v = self.vehiculo_de(track_id)
        if v is None:
            v = self.vehiculos[track_id] = Vehiculo(track_id, frame, segundo, segundo)
        v.lecturas.append((placa, confianza))
        v.ultimo_segundo = segundo
        if len(v.lecturas) < self.votos_minimos:
            return v, False

        primera_vez = v.placa_confirmada is None
        if not self._revotar(v):
            return v, False
        if primera_vez:
            anterior = self._buscar_para_fusion(v)
            if anterior:
                return anterior, self._fusionar(v, anterior)
        return v, True

    def _revotar(self, v: Vehiculo) -> bool:
        """Recalcula la placa del vehículo. Devuelve True si cambió."""
        votada = self.validar(votar_por_caracter(v.lecturas))
        if votada and votada != v.placa_confirmada:
            v.placa_confirmada = votada
            return True
        return False

    def _buscar_para_fusion(self, nuevo: Vehiculo) -> Vehiculo | None:
        """Vehículo ya confirmado, visto hace poco, con placa casi igual a la del nuevo."""
        candidatos = [
            v for v in self.vehiculos.values()
            if v is not nuevo and v.placa_confirmada
            and nuevo.primer_segundo - v.ultimo_segundo <= self.segundos_fusion
            and distancia(v.placa_confirmada, nuevo.placa_confirmada) <= MAX_DIFERENCIAS_FUSION
        ]
        return max(candidatos, key=lambda v: v.ultimo_segundo, default=None)

    def _fusionar(self, nuevo: Vehiculo, anterior: Vehiculo) -> bool:
        """Pasa las lecturas del nuevo al anterior. Devuelve True si la placa del anterior cambió."""
        anterior.lecturas.extend(nuevo.lecturas)
        anterior.ultimo_segundo = max(anterior.ultimo_segundo, nuevo.ultimo_segundo)
        del self.vehiculos[nuevo.track_id]
        self.alias[nuevo.track_id] = anterior.track_id
        for viejo, destino in self.alias.items():   # quien apuntaba al nuevo, ahora al anterior
            if destino == nuevo.track_id:
                self.alias[viejo] = anterior.track_id
        return self._revotar(anterior)

    def confirmados(self) -> list[Vehiculo]:
        return sorted((v for v in self.vehiculos.values() if v.placa_confirmada),
                      key=lambda v: v.primer_segundo)
