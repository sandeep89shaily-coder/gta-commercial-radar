@echo off
setlocal
title GTA Radar - Toronto Meeting PDF Pilot
cd /d "%~dp0"
echo Toronto council agenda-to-PDF pilot: two observed official meetings.
echo This does not change V8 and does not use paid AI.
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (set "PY=py -3") else (set "PY=python")
%PY% -c "import requests,pypdf" >nul 2>nul
if errorlevel 1 (
 echo Missing Python requirements; run: py -3 -m pip install -r requirements.txt
 pause
 exit /b 1
)
%PY% toronto_meeting_pdf_pipeline.py --meetings config\toronto_verified_meeting_seeds.csv --out TORONTO_MEETING_PILOT --max-agendas 2 --max-pdfs 6 --fetch
echo.
echo Reports and audits saved inside TORONTO_MEETING_PILOT
echo.
pause
