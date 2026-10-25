@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title GTA Radar - Early Cues + Capped DeepSeek Research
where py >nul 2>nul
if not errorlevel 1 (set "PY=py -3") else (set "PY=python")
echo Scanning early investment sources; DeepSeek enabled for fresh qualified signals.
echo Software cap US$0.25/day, including other Radar activity recorded in ledger.
echo Provider account billing remains independent. No schedule changes.
%PY% -u early_investment_radar.py --paid-ai
set "CODE=%errorlevel%"
echo Press any key to close.
pause >nul
exit /b %CODE%
