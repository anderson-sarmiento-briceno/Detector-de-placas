@echo off
REM Entrena el detector (o lo CONTINUA si quedo a medias por un apagon, bloqueo o reinicio).
REM Doble clic para ejecutar. El avance se ve en esta ventana; no la cierres mientras entrena.
REM Se guarda al terminar cada epoca: si se apaga el PC, al volver a abrir este archivo sigue donde iba.
REM
REM Para una corrida nueva, cambiar NOMBRE (y BASE si se quiere partir de otro modelo).
set NOMBRE=v3
set BASE=models/detector_colombia.pt

title Entrenando detector %NOMBRE% - no cerrar esta ventana
cd /d "%~dp0"
.venv\Scripts\python -m scripts.entrenar_detector --nombre %NOMBRE% --base %BASE%
echo.
echo ===== Terminado. Puedes cerrar esta ventana. =====
pause
