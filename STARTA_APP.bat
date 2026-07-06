@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM Kor appen redan? Da bara oppna webblasaren.
if exist app.pid (
    set /p GAMMALPID=<app.pid
    tasklist /FI "PID eq %GAMMALPID%" 2>nul | find "%GAMMALPID%" >nul
    if not errorlevel 1 (
        start "" http://127.0.0.1:8750
        exit /b 0
    )
    del app.pid >nul 2>&1
)

REM Starta servern minimerad; den oppnar webblasaren sjalv.
start "JaneStreet-dashboard" /min python app.py
exit /b 0
