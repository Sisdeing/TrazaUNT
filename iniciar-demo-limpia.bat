@echo off
setlocal
cd /d "%~dp0"
echo Iniciando TrazaUNT con una base de demostracion LIMPIA...
echo (la convocatoria FOT-DEMO-002 vuelve a quedar sin postulantes)
where py >nul 2>nul
if errorlevel 1 goto usar_python
py -3 iniciar.py --nueva-demo
goto terminar
:usar_python
where python >nul 2>nul
if errorlevel 1 goto sin_python
python iniciar.py --nueva-demo
goto terminar
:sin_python
echo Instala Python 3.11 o superior y activa el lanzador py.
:terminar
pause
