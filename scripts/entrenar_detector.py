"""Entrena el detector de placas (YOLO, una clase: placa) con Roboflow + frames de video.

Fuentes de datos:
- data/datasets/caracteres (Roboflow helian/placa_colombia): de sus etiquetas solo se usa
  la caja de la placa (los caracteres se descartan).
- data/datasets/detector_video/entrenamiento/dataset (scripts.etiquetas_detector): frames
  del video. El último --fraccion-val del tiempo se separa para validación (por tiempo, no
  al azar: frames vecinos son casi iguales y mezclarlos inflaría la validación).
La prueba final (detector_video/prueba) no se usa aquí: ver --evaluar.

Uso:
    python -m scripts.entrenar_detector --nombre v1
    python -m scripts.entrenar_detector --evaluar models/detector_entrenados/v1/weights/best.pt
"""
import argparse
import logging
import shutil
from pathlib import Path

import numpy as np
import yaml
from ultralytics import YOLO

logger = logging.getLogger(__name__)

RAIZ_DATOS = Path("data/datasets")
ROBOFLOW = RAIZ_DATOS / "caracteres"
VIDEO = RAIZ_DATOS / "detector_video" / "entrenamiento" / "dataset"
PRUEBA = RAIZ_DATOS / "detector_video" / "prueba" / "dataset"
COMBINADO = RAIZ_DATOS / "detector_combinado"
CARPETA_SALIDA = Path("models/detector_entrenados")
CLASE_PLACA_ROBOFLOW = "placa"


def convertir_roboflow(split_origen: str, destino: Path) -> int:
    """Copia imágenes de Roboflow dejando solo la caja de la placa (clase 0)."""
    nombres = yaml.safe_load((ROBOFLOW / "data.yaml").read_text(encoding="utf-8"))["names"]
    id_placa = nombres.index(CLASE_PLACA_ROBOFLOW)
    n = 0
    for img in sorted((ROBOFLOW / split_origen / "images").glob("*.jpg")):
        lineas = []
        for linea in (ROBOFLOW / split_origen / "labels" / f"{img.stem}.txt").read_text().splitlines():
            v = linea.split()
            if not v or int(v[0]) != id_placa:
                continue
            nums = np.array(v[1:], dtype=float)
            if len(nums) == 4:
                cx, cy, w, h = nums
            else:  # polígono → caja
                pts = nums[: len(nums) // 2 * 2].reshape(-1, 2)
                (x1, y1), (x2, y2) = pts.min(0), pts.max(0)
                cx, cy, w, h = (x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1
            lineas.append(f"0 {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
        shutil.copy(img, destino / "images" / f"rf_{img.name}")
        (destino / "labels" / f"rf_{img.stem}.txt").write_text("\n".join(lineas))
        n += 1
    return n


def segundo_de(frame: Path) -> float:
    return float(frame.stem.rsplit("_", 1)[1])


def copiar_video(destino_train: Path, destino_val: Path, fraccion_val: float) -> tuple[int, int]:
    """Copia los frames del video; el último tramo de tiempo va a validación."""
    imagenes = sorted((VIDEO / "images").glob("*.jpg"), key=segundo_de)
    corte = segundo_de(imagenes[0]) + (segundo_de(imagenes[-1]) - segundo_de(imagenes[0])) * (1 - fraccion_val)
    n_train = n_val = 0
    for img in imagenes:
        destino = destino_train if segundo_de(img) < corte else destino_val
        shutil.copy(img, destino / "images" / img.name)
        shutil.copy(VIDEO / "labels" / f"{img.stem}.txt", destino / "labels" / f"{img.stem}.txt")
        if destino is destino_train:
            n_train += 1
        else:
            n_val += 1
    return n_train, n_val


def armar_dataset(fraccion_val: float) -> Path:
    if COMBINADO.exists():
        shutil.rmtree(COMBINADO)
    train, val = COMBINADO / "train", COMBINADO / "val"
    for d in (train, val):
        (d / "images").mkdir(parents=True)
        (d / "labels").mkdir()
    n_rf = convertir_roboflow("train", train)
    n_rf_val = convertir_roboflow("valid", val)
    n_video, n_video_val = copiar_video(train, val, fraccion_val)
    logger.info("Train: %d Roboflow + %d video | Val: %d Roboflow + %d video", n_rf, n_video, n_rf_val, n_video_val)
    return escribir_yaml(COMBINADO, "train/images", "val/images")


def escribir_yaml(raiz: Path, train: str, val: str) -> Path:
    """YAML con ruta absoluta (Ultralytics resuelve las relativas contra su propia carpeta)."""
    ruta = raiz / "data.yaml"
    ruta.write_text(yaml.safe_dump({"path": str(raiz.resolve()), "train": train, "val": val,
                                    "names": {0: "placa"}}), encoding="utf-8")
    return ruta


def evaluar(pesos: Path, imgsz: int) -> None:
    datos = escribir_yaml(PRUEBA, "images", "images")
    r = YOLO(str(pesos)).val(data=str(datos), imgsz=imgsz, conf=0.001, plots=False, verbose=False,
                             project=str(CARPETA_SALIDA), name="_evaluacion", exist_ok=True)
    print(f"{pesos} (imgsz {imgsz}) en prueba: precision={r.box.mp:.3f} recall={r.box.mr:.3f} "
          f"mAP50={r.box.map50:.3f} mAP50-95={r.box.map:.3f}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--nombre", default="v1", help="Nombre de la corrida")
    parser.add_argument("--base", default="models/detector_colombia.pt", help="Pesos de partida")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--epocas", type=int, default=80)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--fraccion-val", type=float, default=0.15)
    parser.add_argument("--evaluar", type=Path, help="Solo evaluar estos pesos en la prueba del video")
    args = parser.parse_args()

    if args.evaluar:
        evaluar(args.evaluar, args.imgsz)
        return
    datos = armar_dataset(args.fraccion_val)
    YOLO(args.base).train(data=str(datos), imgsz=args.imgsz, epochs=args.epocas, batch=args.batch,
                          patience=20, project=str(CARPETA_SALIDA.resolve()), name=args.nombre,
                          exist_ok=True, workers=4, seed=0, plots=True)
    mejor = CARPETA_SALIDA / args.nombre / "weights" / "best.pt"
    evaluar(mejor, args.imgsz)


if __name__ == "__main__":
    main()
