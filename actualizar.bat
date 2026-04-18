@echo off
cd /d "%~dp0"
echo.
echo  VAECOS - Actualizador
echo  =====================
echo.

echo Consultando si hay una nueva version disponible...
python v0.2/cli.py check-update
echo.

set /p CONTINUAR="Descargar e instalar la actualizacion? [s/N]: "
if /i not "%CONTINUAR%"=="s" goto FIN

echo.
echo Descargando actualizacion...
python v0.2/cli.py download-update
if errorlevel 1 goto ERROR

echo.
echo Instalando actualizacion (se hara un backup automatico del codigo actual)...
python v0.2/cli.py apply-update
if errorlevel 1 goto ERROR

echo.
echo Actualizacion completada. Reinicia la aplicacion para usar la nueva version.
goto FIN

:ERROR
echo.
echo Ocurrio un error durante la actualizacion.
echo Revisa los mensajes anteriores para mas informacion.

:FIN
echo.
pause
