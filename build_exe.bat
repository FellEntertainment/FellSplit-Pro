@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if /I "%~1"=="--no-pause" set "NO_PAUSE=1"

where py >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=py"
) else (
    where python >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD (
    echo Python wurde nicht gefunden.
    if not defined NO_PAUSE pause
    exit /b 1
)

echo [1/2] Installiere beziehungsweise aktualisiere Build-Abhaengigkeiten ...
%PYTHON_CMD% -m pip install -r requirements-build.txt
if errorlevel 1 goto :error

echo [2/2] Erstelle FellSplitPro.exe als einzelne Datei ...
%PYTHON_CMD% -m PyInstaller --noconfirm --clean FellSplitPro.spec
if errorlevel 1 goto :error

echo.
echo Fertig: dist\FellSplitPro.exe
if not defined NO_PAUSE pause
exit /b 0

:error
echo.
echo Der Build ist fehlgeschlagen. Lies die Fehlermeldung oberhalb.
if not defined NO_PAUSE pause
exit /b 1
