@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================================
echo  FellSplit Pro 1.3.0 - EXE und Installer bauen
echo ============================================================
echo.

call build_exe.bat --no-pause
if errorlevel 1 goto :error

set "ISCC_PATH="
where ISCC.exe >nul 2>nul
if not errorlevel 1 set "ISCC_PATH=ISCC.exe"
if not defined ISCC_PATH if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC_PATH=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC_PATH if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC_PATH=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC_PATH if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC_PATH=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"

if not defined ISCC_PATH (
    echo.
    echo Inno Setup 6 wurde nicht gefunden.
    where winget >nul 2>nul
    if errorlevel 1 goto :missing_inno
    echo Inno Setup 6 wird jetzt ueber winget installiert ...
    winget install --id JRSoftware.InnoSetup -e -s winget --accept-package-agreements --accept-source-agreements
    if errorlevel 1 goto :missing_inno
    if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC_PATH=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
    if not defined ISCC_PATH if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC_PATH=%ProgramFiles%\Inno Setup 6\ISCC.exe"
    if not defined ISCC_PATH if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC_PATH=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
)

if not defined ISCC_PATH goto :missing_inno

echo.
echo Erstelle den Windows-Installer ...
"%ISCC_PATH%" "FellSplitPro.iss"
if errorlevel 1 goto :error

echo.
echo ============================================================
echo  Fertig: installer\FellSplit-Pro-Setup-1.3.0.exe
echo ============================================================
pause
exit /b 0

:missing_inno
echo.
echo Bitte installiere Inno Setup 6 und starte diese Datei danach erneut:
echo winget install --id JRSoftware.InnoSetup -e -s winget
goto :error

:error
echo.
echo Der Installer-Build ist fehlgeschlagen. Lies die Meldung oberhalb.
pause
exit /b 1
