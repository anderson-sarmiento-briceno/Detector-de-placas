@echo off
REM Entrena el OCR de placas (fast-plate-ocr) con Roboflow + recortes revisados de videos.
REM Doble clic para ejecutar. El avance se ve en esta ventana; no la cierres mientras entrena.
REM Antes: python -m scripts.preparar_ocr_combinado (arma los CSV).
REM Se guarda el mejor modelo en cada epoca (best.keras). Si se corta, volver a abrir este
REM archivo empieza de nuevo; para el OCR son ~30-60 minutos.
set NOMBRE=xs_v3

title Entrenando OCR %NOMBRE% - no cerrar esta ventana
cd /d "%~dp0"
set KERAS_BACKEND=torch
.venv\Scripts\fast-plate-ocr train ^
  --model-config-file models/ocr_base/xs/model_config.yaml ^
  --plate-config-file configs/ocr_plate_config.yaml ^
  --annotations data/datasets/ocr_combinado_train.csv ^
  --val-annotations data/datasets/ocr_combinado_val.csv ^
  --weights-path models/ocr_base/xs/modelo.keras ^
  --epochs 100 --batch-size 64 --lr 0.0003 --early-stopping-patience 30 ^
  --workers 4 --seed 0 --output-dir models/ocr_entrenados/%NOMBRE%
echo.
echo ===== Terminado. Puedes cerrar esta ventana. =====
pause
