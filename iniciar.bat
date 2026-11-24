@echo off
setlocal
cd /d "%~dp0"
echo Iniciando TrazaUNT...
where py >nul 2>nul
if errorlevel 1 goto usar_python
py -3 iniciar.py
goto terminar
:usar_python
where python >nul 2>nul
if errorlevel 1 goto sin_python
python iniciar.py
goto terminar
:sin_python
echo Instala Python 3.11 o superior y activa el lanzador py.
:terminar
pause
