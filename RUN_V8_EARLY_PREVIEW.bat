@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title GTA Radar V8 - Safe Early Signals Preview (Free - No Schedule)
where py >nul 2>nul
if not errorlevel 1 (
  set "PY=py -3"
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python 3 was not found. No files were changed.
    echo Install Python 3 or run the existing Radar Python installation.
    pause
    exit /b 1
  )
  set "PY=python"
)
echo Running PREVIEW on a copy of your existing Radar database.
echo No DeepSeek usage. No Windows schedule will be installed.
%PY% -c "import requests, bs4, pypdf, pandas, openpyxl" >nul 2>nul
if errorlevel 1 (
  echo Installing the same Python requirements used by your existing Radar...
  %PY% -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Python package installation failed. Existing data was not changed.
    pause
    exit /b 1
  )
)
%PY% -u desktop_v8_early_preview.py
set "EXITCODE=%errorlevel%"
echo.
if not "%EXITCODE%"=="0" (
  echo Preview encountered a problem. Look in your early preview folder,
  echo under Desktop\new data\GTA_RADAR_V8_EARLY_PREVIEW\GTA_RADAR_RESULTS.
)
echo Done. Press any key to close this window.
pause >nul
exit /b %EXITCODE%
