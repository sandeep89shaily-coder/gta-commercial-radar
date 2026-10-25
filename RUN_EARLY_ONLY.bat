@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title GTA Radar - Early Cues ONLY (Free)
echo Only the early-cue collectors will run. DeepSeek is OFF.
echo This uses the existing isolated preview database and does NOT install a schedule.
where py >nul 2>nul
if not errorlevel 1 (
  set "PY=py -3"
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python 3 is not installed. No Radar data changed.
    pause
    exit /b 1
  )
  set "PY=python"
)
%PY% -u run_desktop_early_only.py
set "STATUS=%errorlevel%"
echo.
if not "%STATUS%"=="0" (
  echo Some sources need attention. Open GTA_RADAR_EARLY_ONLY.html in the preview results.
)
echo Press any key to close.
pause >nul
exit /b %STATUS%
