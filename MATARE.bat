@echo off
chcp 65001 >nul
title Riskmatare - ETF
cd /d "%~dp0"
python risk_monitor.py
pause
