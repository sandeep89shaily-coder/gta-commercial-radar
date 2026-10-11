@echo off
setlocal
cd /d "%~dp0"
title GTA Commercial Radar - Easy Start
where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
echo.
echo GTA COMMERCIAL RADAR - EASY START
echo ----------------------------------
%PY% --version >nul 2>nul
if errorlevel 1 (
 echo Python was not found. Install Python 3 and select "Add Python to PATH".
 echo Your files have not been changed.
 pause
 exit /b 1
)
%PY% -c "import requests, bs4, pypdf, pandas, openpyxl" >nul 2>nul
if errorlevel 1 (
 echo Installing required Python packages - once only...
 %PY% -m pip install -r requirements.txt
 if errorlevel 1 (
  echo Python package installation failed. No original data was modified.
  pause
  exit /b 1
 )
)
%PY% simple_start.py
echo.
pause
