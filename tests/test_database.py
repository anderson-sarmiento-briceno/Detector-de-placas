from src.database import BaseDatos


def test_buscar_y_registrar(tmp_path):
    bd = BaseDatos(tmp_path / "placas.db")
    assert bd.buscar("ABC123") is None
    bd.agregar_placa("ABC123", "Reportado")
    bd.agregar_placa("XYZ12D")
    assert bd.buscar("ABC123") == "Reportado"
    assert bd.buscar("XYZ12D") == ""          # está, aunque sin motivo
    assert bd.contar_placas() == 2

    bd.registrar_deteccion("v.mp4", 10, 0.4, "ABC123", 0.8, True)
    fila = bd.conexion.execute("SELECT video, placa, coincidencia FROM detecciones").fetchone()
    assert fila == ("v.mp4", "ABC123", 1)
    bd.cerrar()
