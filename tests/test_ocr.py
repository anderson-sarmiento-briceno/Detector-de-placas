from src.ocr import unir_lineas_grandes


def caja(x1, y1, x2, y2):
    """Caja de 4 puntos en el orden normal de EasyOCR (sup-izq, sup-der, inf-der, inf-izq)."""
    return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]


def test_una_linea_ignora_municipio():
    resultados = [(caja(10, 10, 200, 60), "ABC-123", 0.9),
                  (caja(40, 70, 170, 85), "BOGOTA", 0.8)]
    assert unir_lineas_grandes(resultados, 0.6) == ("ABC-123", 0.9)


def test_moto_dos_lineas_en_orden():
    resultados = [(caja(20, 60, 120, 100), "12D", 0.7),
                  (caja(20, 10, 120, 50), "ABC", 0.9)]
    assert unir_lineas_grandes(resultados, 0.6) == ("ABC12D", 0.7)


def test_texto_partido_en_la_misma_linea():
    resultados = [(caja(110, 12, 200, 60), "123", 0.8),
                  (caja(10, 10, 100, 58), "ABC", 0.9)]
    assert unir_lineas_grandes(resultados, 0.6) == ("ABC123", 0.8)


def test_caja_con_puntos_en_otro_orden_no_falla():
    # Caja "al revés" (empieza por abajo): antes daba alto negativo y se caía
    invertida = [[10, 60], [200, 60], [200, 10], [10, 10]]
    assert unir_lineas_grandes([(invertida, "ABC123", 0.5)], 0.6) == ("ABC123", 0.5)


def test_caja_sin_alto_devuelve_vacio():
    plana = [[10, 10], [200, 10], [200, 10], [10, 10]]
    assert unir_lineas_grandes([(plana, "X", 0.5)], 0.6) == ("", 0.0)
