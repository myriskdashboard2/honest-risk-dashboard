@echo off
chcp 65001 >nul
title Meritlista + Benchmark
cd /d "%~dp0"
python track_record.py
echo.
pause
