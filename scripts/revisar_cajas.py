"""Revisión humana de las cajas dudosas del detector, en páginas de 20 (cuadrícula).

Cada caja trae una sugerencia (borde VERDE = placa, ROJO = no placa). Solo hay que
corregir las que estén mal:
    clic          cambia la caja: placa → no placa → ignorar (gris) → placa ...
    Enter/espacio confirma la página y pasa a la siguiente
    z             vuelve a la página anterior
    q             guarda y sale (se puede continuar después; queda en decisiones.csv)

Criterio: es "placa" todo lo que un humano reconoce como placa, aunque no se lea completa.
"ignorar" es para lo que no se puede decidir (tapada a medias, demasiado borrosa).

Uso:
    python -m scripts.revisar_cajas --carpeta data/datasets/detector_video/entrenamiento
"""
import argparse
import csv
from pathlib import Path

import cv2
import numpy as np

from scripts.etiquetas_detector import (IGNORAR, NO_PLACA, PLACA, REVISAR, clase_final, clave,
                                        leer_cajas, leer_decisiones)

VENTANA = "Revision: clic = cambiar | Enter = siguiente pagina | z = atras | q = salir"
COLUMNAS, FILAS = 5, 4
ANCHO_CELDA, ALTO_CELDA = 300, 170
CONF_OCR_SUGERIR_PLACA = 0.25
COLORES = {PLACA: (0, 200, 0), NO_PLACA: (0, 0, 230), IGNORAR: (150, 150, 150)}
SIGUIENTE = {PLACA: NO_PLACA, NO_PLACA: IGNORAR, IGNORAR: PLACA}


def sugerencia(fila: dict) -> str:
    """Placa si el OCR ve una placa colombiana, aunque con poca confianza."""
    if int(fila["placa_valida"]) and float(fila["conf_ocr"]) >= CONF_OCR_SUGERIR_PLACA:
        return PLACA
    return NO_PLACA


def miniatura(imagen: np.ndarray, fila: dict) -> np.ndarray:
    """Recorte con contexto alrededor de la caja, del tamaño de una celda."""
    x1, y1, x2, y2 = (int(fila[k]) for k in ("x1", "y1", "x2", "y2"))
    w, h = x2 - x1, y2 - y1
    alto_img, ancho_img = imagen.shape[:2]
    mx, my = max(w, 60), max(h * 2, 40)
    cx1, cy1 = max(0, x1 - mx), max(0, y1 - my)
    cx2, cy2 = min(ancho_img, x2 + mx), min(alto_img, y2 + my)
    recorte = imagen[cy1:cy2, cx1:cx2].copy()
    cv2.rectangle(recorte, (x1 - cx1, y1 - cy1), (x2 - cx1, y2 - cy1), (0, 255, 255), 1)
    return cv2.resize(recorte, (ANCHO_CELDA, ALTO_CELDA - 22), interpolation=cv2.INTER_CUBIC)


def dibujar_pagina(miniaturas: list[np.ndarray], filas: list[dict], estados: list[str],
                   pagina: int, paginas: int) -> np.ndarray:
    lienzo = np.full((FILAS * ALTO_CELDA + 36, COLUMNAS * ANCHO_CELDA, 3), 40, np.uint8)
    cv2.putText(lienzo, f"Pagina {pagina + 1}/{paginas}   verde=placa  rojo=no placa  gris=ignorar",
                (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    for k, (mini, fila, estado) in enumerate(zip(miniaturas, filas, estados)):
        x, y = (k % COLUMNAS) * ANCHO_CELDA, 36 + (k // COLUMNAS) * ALTO_CELDA
        lienzo[y:y + ALTO_CELDA - 22, x:x + ANCHO_CELDA] = mini
        cv2.rectangle(lienzo, (x + 1, y + 1), (x + ANCHO_CELDA - 2, y + ALTO_CELDA - 2), COLORES[estado], 3)
        cv2.putText(lienzo, f"{fila['texto'] or '-'} {float(fila['conf_ocr']):.2f}",
                    (x + 6, y + ALTO_CELDA - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    return lienzo


def guardar(ruta: Path, decisiones: dict[str, str]) -> None:
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        escritor.writerow(["caja", "decision"])
        escritor.writerows(decisiones.items())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--carpeta", type=Path, required=True)
    args = parser.parse_args()

    ruta_decisiones = args.carpeta / "decisiones.csv"
    decisiones = leer_decisiones(args.carpeta)
    pendientes = [f for f in leer_cajas(args.carpeta) if f["x1"] and clase_final(f, decisiones) == REVISAR]
    por_pagina = COLUMNAS * FILAS
    paginas = [pendientes[i:i + por_pagina] for i in range(0, len(pendientes), por_pagina)]
    print(f"{len(pendientes)} cajas por revisar en {len(paginas)} páginas")
    if not paginas:
        return

    clics: list[tuple[int, int]] = []
    cv2.namedWindow(VENTANA)
    cv2.setMouseCallback(VENTANA, lambda ev, x, y, *_: clics.append((x, y)) if ev == cv2.EVENT_LBUTTONDOWN else None)
    p = 0
    while 0 <= p < len(paginas):
        filas = paginas[p]
        miniaturas = [miniatura(cv2.imread(str(args.carpeta / "images" / f["frame"])), f) for f in filas]
        estados = [decisiones.get(clave(f)) or sugerencia(f) for f in filas]
        while True:
            cv2.imshow(VENTANA, dibujar_pagina(miniaturas, filas, estados, p, len(paginas)))
            tecla = cv2.waitKey(30) & 0xFF
            for x, y in clics:
                k = ((y - 36) // ALTO_CELDA) * COLUMNAS + x // ANCHO_CELDA
                if y >= 36 and 0 <= k < len(filas):
                    estados[k] = SIGUIENTE[estados[k]]
            clics.clear()
            if tecla in (13, 32, ord("z"), ord("q")) or cv2.getWindowProperty(VENTANA, cv2.WND_PROP_VISIBLE) < 1:
                break
        if tecla in (13, 32):
            for f, estado in zip(filas, estados):
                decisiones[clave(f)] = estado
            guardar(ruta_decisiones, decisiones)
            p += 1
        elif tecla == ord("z"):
            p = max(0, p - 1)
        else:
            break
    cv2.destroyAllWindows()
    restantes = sum(1 for f in pendientes if clave(f) not in decisiones)
    print(f"Decisiones guardadas en {ruta_decisiones}. Quedan {restantes} cajas por revisar.")


if __name__ == "__main__":
    main()
