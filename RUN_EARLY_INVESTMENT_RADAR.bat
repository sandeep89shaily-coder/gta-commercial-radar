@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title GTA Radar - Early Investment Sources (Free Preview)
where py >nul 2>nul
if not errorlevel 1 (set "PY=py -3") else (set "PY=python")
echo Scanning 17 existing early sources plus four new investment feeds.
echo Original V8 collectors OFF. DeepSeek OFF. No scheduler changes.
%PY% -u early_investment_radar.py
set "CODE=%errorlevel%"
echo.
if not "%CODE%"=="0" echo Partial sources or run error. See unified HTML report and EARLY_LOGS.
echo Press any key to close.
pause >nul
exit /b %CODE%
