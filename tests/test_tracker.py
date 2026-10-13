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


def test_fusiona_cuando_la_placa_se_corrige_despues():
    # Caso real: el ID nuevo se confirma primero con lecturas lejanas y erradas
    # (WAW450, nada parecido) y solo después se corrige a la placa ya vista.
    v = nueva_votacion(2, segundos_fusion=10)
    for i in range(3):
        v.agregar(88, "KAV637", 0.9, i, 26.0 + i)          # visto hasta 28 s
    for i in range(2):
        v.agregar(104, "WAW450", 0.5, 100 + i, 37.0)
    assert len(v.confirmados()) == 2                        # aún no se parecen
    for i in range(3):
        v.agregar(104, "KAV637", 0.9, 110 + i, 38.0 + i)
    assert [x.placa_confirmada for x in v.confirmados()] == ["KAV637"]
    assert v.vehiculo_de(104) is v.vehiculo_de(88)
    assert v.vehiculo_de(88).primer_segundo == 26.0


def test_fusiona_vehiculos_que_se_solapan_en_el_tiempo():
    v = nueva_votacion(2, segundos_fusion=10)
    for i in range(2):
        v.agregar(190, "PUM731", 0.9, i, 113.7 + i)        # 113.7 - 114.7 s
        v.agregar(193, "PUM731", 0.9, 10 + i, 114.0 + i)   # 114.0 - 115.0 s
    assert len(v.confirmados()) == 1
    assert v.confirmados()[0].primer_segundo == 113.7


def test_placa_identica_se_fusiona_con_ventana_mas_larga():
    v = VotacionPlacas(2, validar_colombia, segundos_fusion=10, segundos_fusion_misma_placa=60)
    for i in range(2):
        v.agregar(93, "OEQ81E", 0.9, i, 28.5)
    for i in range(2):
        v.agregar(115, "OEQ81E", 0.9, 100 + i, 40.1)      # 11.6 s después, idéntica
    for i in range(2):
        v.agregar(120, "OEQ81F", 0.9, 200 + i, 60.0)      # casi igual pero 20 s después
    assert [x.placa_confirmada for x in v.confirmados()] == ["OEQ81E", "OEQ81F"]


def test_no_fusiona_si_paso_mucho_tiempo():
    v = nueva_votacion(2, segundos_fusion=3)
    for i in range(2):
        v.agregar(10, "DEO81E", 0.9, i, 10.0)
    for i in range(2):
        v.agregar(11, "OEO81E", 0.9, 100 + i, 60.0)
    assert len(v.confirmados()) == 2
