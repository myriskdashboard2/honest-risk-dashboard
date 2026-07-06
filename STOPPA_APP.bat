@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist app.pid (
    echo Appen verkar inte vara igang.
    ping -n 3 127.0.0.1 >nul
    exit /b 0
)

set /p APPPID=<app.pid
taskkill /PID %APPPID% /F >nul 2>&1
del app.pid >nul 2>&1
echo Dashboarden ar stoppad. Ha det bra!
ping -n 3 127.0.0.1 >nul
exit /b 0
