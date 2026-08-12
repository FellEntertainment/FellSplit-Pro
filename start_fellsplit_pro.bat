@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=py"
) else (
    where python >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD (
    echo Python wurde nicht gefunden.
    echo Installiere Python 3.10 oder neuer von python.org und aktiviere "Add Python to PATH".
    pause
    exit /b 1
)

%PYTHON_CMD% -c "import customtkinter, pystray, PIL" >nul 2>nul
if errorlevel 1 (
    echo FellSplit-Pro-Komponenten werden einmalig installiert ...
    %PYTHON_CMD% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Installation fehlgeschlagen.
        pause
        exit /b 1
    )
)

where pyw >nul 2>nul
if not errorlevel 1 (
    start "" pyw FellSplitPro.pyw --launch-check
) else (
    where pythonw >nul 2>nul
    if not errorlevel 1 (
        start "" pythonw FellSplitPro.pyw --launch-check
    ) else (
        echo Der fensterlose Python-Launcher pyw/pythonw wurde nicht gefunden.
        echo Installiere die vollstaendige Python-Version von python.org.
        pause
        exit /b 1
    )
)
if errorlevel 1 pause
