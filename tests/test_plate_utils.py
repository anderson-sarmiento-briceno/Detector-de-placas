import pytest

from src.plate_utils import corregir_colombia, normalizar, validar_placa


def test_normalizar_quita_guiones_y_espacios():
    assert normalizar(" abc-123 ") == "ABC123"
    assert normalizar("AB.C 1·23") == "ABC123"


@pytest.mark.parametrize("crudo, esperado", [
    ("ABC123", "ABC123"),
    ("abc-123", "ABC123"),
    ("A8C1Z3", "ABC123"),   # 8→B en letra, Z→2 en número
    ("0BC12O", "OBC120"),   # 0→O en letra, O→0 en número
    ("5GA1B4", "SGA184"),
])
def test_colombia_carro(crudo, esperado):
    assert validar_placa(crudo, "colombia") == esperado


@pytest.mark.parametrize("crudo, esperado", [
    ("ABC12D", "ABC12D"),   # moto tal cual
    ("abc 12d", "ABC12D"),
    ("WRG-22H", "WRG22H"),
    ("W8G2ZH", "WBG22H"),   # 8→B en letra, Z→2 en número
    ("ABCI2K", "ABC12K"),   # I→1 en número; K no es número → plantilla moto
])
def test_colombia_moto(crudo, esperado):
    assert validar_placa(crudo, "colombia") == esperado


@pytest.mark.parametrize("crudo", ["ABC12", "ABC1234", "1234AB","", "BOGOTA", "VBC75", "12ABCD"])
def test_colombia_invalidas(crudo):
    assert validar_placa(crudo, "colombia") is None


def test_corregir_colombia_ignora_largo_distinto_de_6():
    assert corregir_colombia("A8C12") == "A8C12"


@pytest.mark.parametrize("crudo, esperado", [
    ("7ABC123", "7ABC123"),
    ("ab 12-cd", "AB12CD"),
    ("A8C1Z3", "A8C1Z3"),   # en genérico no se corrige por posición
])
def test_generico_validas(crudo, esperado):
    assert validar_placa(crudo, "generico") == esperado


@pytest.mark.parametrize("crudo", ["AB12", "ABCDE12345", "", "--"])
def test_generico_invalidas(crudo):
    assert validar_placa(crudo, "generico") is None


def test_formato_desconocido():
    with pytest.raises(ValueError):
        validar_placa("ABC123", "peru")
