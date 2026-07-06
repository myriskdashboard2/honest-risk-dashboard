@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ================================================================
echo   INSTALLERA riskmataren pa den har datorn
echo ================================================================
echo.

REM 1) Finns Python?
python --version >nul 2>&1
if errorlevel 1 (
    echo  [FEL] Python hittades inte pa den har datorn.
    echo.
    echo  Gor sa har forst:
    echo   1. Ga till  https://www.python.org/downloads/
    echo   2. Ladda ner och installera Python 3.
    echo   3. VIKTIGT: bocka i "Add Python to PATH" under installationen.
    echo   4. Kor den har INSTALLERA.bat igen.
    echo.
    pause
    exit /b 1
)

echo  Python hittad:
python --version
echo.
echo  Installerar bibliotek (yfinance, pandas, numpy)...
echo.
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo.
echo ================================================================
echo   KLART! Nu kan du kora:
echo     RISK.bat     = full riskrapport (en gang)
echo     MATARE.bat   = live-matare (uppdaterar var 5:e minut)
echo ================================================================
echo.
pause
