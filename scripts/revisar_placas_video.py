"""Revisión humana de las placas confirmadas en un video (una imagen por vehículo).

Cada celda muestra el recorte más cercano del vehículo y la placa que confirmó el sistema.
    (nada)          borde VERDE = la lectura está bien
    clic izquierdo  alterna VERDE ↔ ROJO (rojo = mal leída o no es placa → no se usa)
    clic derecho    escribir la placa correcta en la terminal (borde AZUL = corregida)
    Enter/espacio   confirma la página y pasa a la siguiente
    z               página anterior
    q               guardar y salir (se puede continuar después)

Las decisiones se guardan en la columna `decision` de vehiculos.csv (ok | mal | corregida).

Uso:
    python -m scripts.revisar_placas_video --carpeta data/datasets/ocr_video/<video>
"""
import argparse
import csv
from pathlib import Path

import cv2
import numpy as np

from src.plate_utils import FORMATO_COLOMBIA, validar_placa

VENTANA = "Placas: clic = bien/mal | clic derecho = corregir | Enter = siguiente | z = atras | q = salir"
COLUMNAS, FILAS = 5, 4
ANCHO, ALTO = 300, 180
COLORES = {"ok": (0, 200, 0), "mal": (0, 0, 230), "corregida": (230, 120, 0)}


def leer(ruta: Path) -> list[dict]:
    with open(ruta, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def guardar(ruta: Path, vehiculos: list[dict]) -> None:
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=list(vehiculos[0]))
        escritor.writeheader()
        escritor.writerows(vehiculos)


def celda(carpeta: Path, v: dict, estado: str) -> np.ndarray:
    img = cv2.imread(str(carpeta / "recortes" / v["mejor_recorte"]))
    img = cv2.resize(img, (ANCHO, ALTO - 34), interpolation=cv2.INTER_CUBIC)
    lienzo = np.full((ALTO, ANCHO, 3), 40, np.uint8)
    lienzo[:ALTO - 34] = img
    cv2.putText(lienzo, v["placa"], (8, ALTO - 9), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
    cv2.rectangle(lienzo, (1, 1), (ANCHO - 2, ALTO - 2), COLORES[estado], 4)
    return lienzo


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--carpeta", type=Path, required=True)
    args = parser.parse_args()

    ruta = args.carpeta / "vehiculos.csv"
    vehiculos = leer(ruta)
    pendientes = [i for i, v in enumerate(vehiculos) if not v["decision"]]
    por_pagina = COLUMNAS * FILAS
    paginas = [pendientes[i:i + por_pagina] for i in range(0, len(pendientes), por_pagina)]
    print(f"{len(pendientes)} vehículos por revisar en {len(paginas)} páginas")
    if not paginas:
        return

    clics: list[tuple[int, int, int]] = []

    def raton(evento, x, y, *_):
        if evento in (cv2.EVENT_LBUTTONDOWN, cv2.EVENT_RBUTTONDOWN):
            clics.append((evento, x, y))

    cv2.namedWindow(VENTANA)
    cv2.setMouseCallback(VENTANA, raton)
    p = 0
    while 0 <= p < len(paginas):
        indices = paginas[p]
        estados = {i: vehiculos[i]["decision"] or "ok" for i in indices}
        cv2.setWindowTitle(VENTANA, f"Pagina {p + 1}/{len(paginas)} - {VENTANA}")
        lienzo = np.full((FILAS * ALTO + 40, COLUMNAS * ANCHO, 3), 40, np.uint8)
        cv2.putText(lienzo, f"Pagina {p + 1}/{len(paginas)}", (10, 28), cv2.FONT_HERSHEY_SIMPLEX,
                    0.8, (255, 255, 255), 2)

        def pintar(i: int) -> None:
            k = indices.index(i)
            y, x = 40 + (k // COLUMNAS) * ALTO, (k % COLUMNAS) * ANCHO
            lienzo[y:y + ALTO, x:x + ANCHO] = celda(args.carpeta, vehiculos[i], estados[i])

        for i in indices:
            pintar(i)
        while True:
            cv2.imshow(VENTANA, lienzo)
            tecla = cv2.waitKey(30) & 0xFF
            for evento, x, y in clics:
                k = ((y - 40) // ALTO) * COLUMNAS + x // ANCHO
                if y < 40 or not 0 <= k < len(indices):
                    continue
                i = indices[k]
                if evento == cv2.EVENT_LBUTTONDOWN:
                    estados[i] = "mal" if estados[i] != "mal" else "ok"
                else:
                    aviso = lienzo.copy()
                    cv2.rectangle(aviso, (0, 0), (aviso.shape[1], 40), (0, 140, 255), -1)
                    cv2.putText(aviso, "Escribe la placa correcta en la TERMINAL de VS Code y presiona Enter",
                                (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 0), 2)
                    cv2.imshow(VENTANA, aviso)
                    cv2.waitKey(1)
                    texto = input(f"Placa correcta para {vehiculos[i]['placa']} (Enter = cancelar): ").strip()
                    placa = validar_placa(texto, FORMATO_COLOMBIA) if texto else None
                    if placa:
                        vehiculos[i]["placa"] = placa
                        estados[i] = "corregida"
                    elif texto:
                        print(f"'{texto}' no es una placa colombiana válida (ABC123 o ABC12D)")
                pintar(i)
            clics.clear()
            if tecla in (13, 32, ord("z"), ord("q")) or cv2.getWindowProperty(VENTANA, cv2.WND_PROP_VISIBLE) < 1:
                break
        if tecla in (13, 32):
            for i in indices:
                vehiculos[i]["decision"] = estados[i]
            guardar(ruta, vehiculos)
            p += 1
        elif tecla == ord("z"):
            p = max(0, p - 1)
        else:
            break
    cv2.destroyAllWindows()
    restantes = sum(1 for v in vehiculos if not v["decision"])
    print(f"Guardado en {ruta}. Quedan {restantes} vehículos por revisar.")


if __name__ == "__main__":
    main()
