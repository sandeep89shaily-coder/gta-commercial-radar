@echo off
setlocal
title GTA Radar - Toronto Verified Reports Pilot
cd /d "%~dp0"
echo Collecting four documented Toronto municipal reports from the verified queue.
echo This does not access secure.toronto.ca, update V8, or use paid AI.
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (set "PY=py -3") else (set "PY=python")
%PY% -c "import requests,pypdf" >nul 2>nul
if errorlevel 1 (
  echo Missing requirements: py -3 -m pip install -r requirements.txt
  pause
  exit /b 1
)
%PY% toronto_verified_report_queue.py --queue config\toronto_verified_report_queue.csv --out TORONTO_VERIFIED_REPORTS --max-files 4 --fetch
echo.
echo Review TORONTO_VERIFIED_REPORTS\VERIFIED_REPORT_FETCH_AUDIT.csv.
pause
