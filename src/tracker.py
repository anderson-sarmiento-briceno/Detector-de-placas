"""Votación temporal: junta las lecturas de un mismo vehículo y confirma una sola placa.

El OCR se equivoca en 1-2 caracteres de forma distinta en cada frame
(IEO81E, DEO81E, OEO81E...). En vez de exigir que el texto completo se repita,
se vota **carácter por carácter** entre todas las lecturas del mismo vehículo
(mismo `track_id` de YOLO).

Si el seguimiento pierde un vehículo un momento y le asigna un ID nuevo, se
**fusiona** con el anterior cuando su placa difiere en máximo 1 carácter y
apareció pocos segundos después. Se revisa cada vez que la placa de un vehículo
cambia (no solo la primera vez): la primera confirmación suele salir de lecturas
lejanas y erradas, y solo al corregirse se parece a la del vehículo anterior.
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


def separacion_segundos(a: "Vehiculo", b: "Vehiculo") -> float:
    """Segundos entre los intervalos en que se vio cada vehículo (≤ 0 si se solapan)."""
    return max(a.primer_segundo, b.primer_segundo) - min(a.ultimo_segundo, b.ultimo_segundo)


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
                 segundos_fusion: float, segundos_fusion_misma_placa: float | None = None) -> None:
        """`validar` vuelve a comprobar el formato del texto votado (p. ej. validar_placa).

        `segundos_fusion` aplica a placas que difieren en 1 carácter; las idénticas se
        fusionan hasta `segundos_fusion_misma_placa` (no hay dos vehículos con la misma placa).
        """
        self.votos_minimos = votos_minimos
        self.validar = validar
        self.segundos_fusion = segundos_fusion
        self.segundos_fusion_misma_placa = max(segundos_fusion, segundos_fusion_misma_placa or 0)
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

        if not self._revotar(v):
            return v, False
        anterior = self._buscar_para_fusion(v)
        if anterior:
            self._fusionar(v, anterior)
            return anterior, True
        return v, True

    def _revotar(self, v: Vehiculo) -> bool:
        """Recalcula la placa del vehículo. Devuelve True si cambió."""
        votada = self.validar(votar_por_caracter(v.lecturas))
        if votada and votada != v.placa_confirmada:
            v.placa_confirmada = votada
            return True
        return False

    def _buscar_para_fusion(self, nuevo: Vehiculo) -> Vehiculo | None:
        """Otro vehículo confirmado, visto cerca en el tiempo, con placa casi igual a la del nuevo."""
        def se_fusiona(v: Vehiculo) -> bool:
            diferencias = distancia(v.placa_confirmada, nuevo.placa_confirmada)
            limite = self.segundos_fusion_misma_placa if diferencias == 0 else self.segundos_fusion
            return diferencias <= MAX_DIFERENCIAS_FUSION and separacion_segundos(v, nuevo) <= limite

        candidatos = [v for v in self.vehiculos.values()
                      if v is not nuevo and v.placa_confirmada and se_fusiona(v)]
        return max(candidatos, key=lambda v: v.ultimo_segundo, default=None)

    def _fusionar(self, nuevo: Vehiculo, anterior: Vehiculo) -> bool:
        """Pasa las lecturas del nuevo al anterior. Devuelve True si la placa del anterior cambió."""
        anterior.lecturas.extend(nuevo.lecturas)
        if nuevo.primer_segundo < anterior.primer_segundo:
            anterior.primer_segundo, anterior.primer_frame = nuevo.primer_segundo, nuevo.primer_frame
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
