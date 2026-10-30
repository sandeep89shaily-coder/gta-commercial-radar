@echo off
setlocal
title GTA Radar - AI Budget Diagnostic (No API Calls)
cd /d "%~dp0"
set "RESULTS=%USERPROFILE%\Desktop\new data\GTA_RADAR_RESULTS"
if not exist "%RESULTS%\" set "RESULTS=%USERPROFILE%\OneDrive\Desktop\new data\GTA_RADAR_RESULTS"
if not exist "%RESULTS%\" (
 echo ERROR: GTA_RADAR_RESULTS directory not found.
 echo This diagnostic made no requests and changed no budget.
 pause
 exit /b 1
)
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (set "PY=py -3") else (set "PY=python")
echo Checking the existing shared DeepSeek ledger read-only...
%PY% municipal_ai_budget_diagnostic.py --results "%RESULTS%"
echo.
echo Please screenshot this window or copy its text into ChatGPT.
echo No DeepSeek API requests were made.
pause
