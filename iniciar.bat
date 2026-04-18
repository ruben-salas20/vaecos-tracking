@echo off
cd /d "%~dp0"
echo.
echo  Iniciando VAECOS App...
echo  Abre tu navegador en: http://127.0.0.1:8765
echo.
echo  Presiona Ctrl+C para detener la aplicacion.
echo.
python v0.3/server.py
pause
