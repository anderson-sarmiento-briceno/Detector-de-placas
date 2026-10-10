from src.plate_utils import validar_placa
from src.tracker import VotacionPlacas, distancia, firma, votar_por_caracter


def validar_colombia(texto: str) -> str | None:
    return validar_placa(texto, "colombia")


def nueva_votacion(votos_minimos: int = 3, segundos_fusion: float = 3.0) -> VotacionPlacas:
    return VotacionPlacas(votos_minimos, validar_colombia, segundos_fusion)


def test_firma_y_distancia():
    assert firma("ABC123") == "LLLNNN"
    assert firma("ABC12D") == "LLLNNL"
    assert distancia("DEO81E", "OEO81E") == 1
    assert distancia("ABC123", "ABC12") == 6


def test_voto_por_caracter_recupera_placa_sin_lectura_perfecta():
    # Caso real de la moto: ninguna lectura se repite mucho, pero cada posición sí
    lecturas = [(p, 0.5) for p in ["IEO81E", "DEO81E", "OEO81E", "DEO81E", "NEO81E",
                                   "DZO81E", "DEQ81E", "DEO61E", "DED81E"]]
    assert votar_por_caracter(lecturas) == "DEO81E"


def test_voto_ignora_lecturas_con_otro_patron():
    lecturas = [("NRZ267", 0.5), ("NRZ267", 0.5), ("NRZ26T", 0.9)]
    assert votar_por_caracter(lecturas) == "NRZ267"


def test_empate_se_decide_por_confianza():
    assert votar_por_caracter([("ABC123", 0.9), ("ABC128", 0.2)]) == "ABC123"


def test_no_confirma_antes_de_votos_minimos():
    v = nueva_votacion(3)
    assert v.agregar(1, "CTB816", 0.9, 0, 0.0)[1] is False
    assert v.agregar(1, "CTB816", 0.9, 2, 0.1)[1] is False
    assert v.vehiculo_de(1).placa_confirmada is None
    vehiculo, cambio = v.agregar(1, "CTB810", 0.5, 4, 0.2)
    assert cambio and vehiculo.placa_confirmada == "CTB816"


def test_no_reporta_cambio_si_la_placa_sigue_igual():
    v = nueva_votacion(2)
    v.agregar(1, "CTB816", 0.9, 0, 0.0)
    assert v.agregar(1, "CTB816", 0.9, 2, 0.1)[1] is True
    assert v.agregar(1, "CTB816", 0.9, 4, 0.2)[1] is False


def test_vehiculos_distintos_no_se_fusionan():
    v = nueva_votacion(2)
    for i in range(2):
        v.agregar(1, "CTB816", 0.9, i, 0.0)
        v.agregar(2, "HCV948", 0.9, i, 0.0)
    assert [x.placa_confirmada for x in v.confirmados()] == ["CTB816", "HCV948"]


def test_fusiona_vehiculo_que_el_seguimiento_perdio():
    v = nueva_votacion(2, segundos_fusion=3)
    for i in range(3):
        v.agregar(10, "DEO81E", 0.9, i, 36.0 + i)        # visto hasta 38 s
    v.agregar(11, "OEO81E", 0.5, 50, 39.5)                # ID nuevo 1,5 s después
    vehiculo, _ = v.agregar(11, "OEO81E", 0.5, 52, 39.6)
    assert vehiculo.track_id == 10                        # se unió al anterior
    assert len(v.confirmados()) == 1
    assert v.vehiculo_de(11) is v.vehiculo_de(10)
    assert v.vehiculo_de(10).placa_confirmada == "DEO81E"
    v.agregar(11, "DEO81E", 0.9, 54, 39.7)                # lecturas futuras del ID 11 van al 10
    assert len(v.vehiculo_de(10).lecturas) == 6


def test_no_fusiona_si_paso_mucho_tiempo():
    v = nueva_votacion(2, segundos_fusion=3)
    for i in range(2):
        v.agregar(10, "DEO81E", 0.9, i, 10.0)
    for i in range(2):
        v.agregar(11, "OEO81E", 0.9, 100 + i, 60.0)
    assert len(v.confirmados()) == 2
