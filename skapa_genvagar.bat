@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Skapar ikoner ...
python gen_ikoner.py
if errorlevel 1 (
    echo [FEL] Kunde inte skapa ikonerna. Ar Python installerat?
    pause
    exit /b 1
)

echo Skapar genvagar pa skrivbordet ...
powershell -NoProfile -Command ^
  "$W = New-Object -ComObject WScript.Shell;" ^
  "$desk = [Environment]::GetFolderPath('Desktop');" ^
  "$s = $W.CreateShortcut(\"$desk\\Jane Street - STARTA.lnk\");" ^
  "$s.TargetPath = '%~dp0STARTA_APP.bat';" ^
  "$s.WorkingDirectory = '%~dp0';" ^
  "$s.IconLocation = '%~dp0ikon_start.ico';" ^
  "$s.Description = 'Starta riskdashboarden';" ^
  "$s.Save();" ^
  "$t = $W.CreateShortcut(\"$desk\\Jane Street - STOPPA.lnk\");" ^
  "$t.TargetPath = '%~dp0STOPPA_APP.bat';" ^
  "$t.WorkingDirectory = '%~dp0';" ^
  "$t.IconLocation = '%~dp0ikon_stopp.ico';" ^
  "$t.Description = 'Stoppa riskdashboarden';" ^
  "$t.Save()"

if errorlevel 1 (
    echo [FEL] Kunde inte skapa genvagarna.
    pause
    exit /b 1
)
echo.
echo KLART! Tva ikoner ligger nu pa skrivbordet:
echo    "Jane Street - STARTA"  = oppnar dashboarden i webblasaren
echo    "Jane Street - STOPPA"  = stanger den
echo.
pause
