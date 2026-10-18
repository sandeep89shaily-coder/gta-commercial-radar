@echo off
setlocal
cd /d "%~dp0"
title GTA Radar V6 - Daily Collection and Investigation
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "%~dp0v6_daily_pipeline.py" %*
) else (
  python "%~dp0v6_daily_pipeline.py" %*
)
set "RESULT=%errorlevel%"
if not "%RESULT%"=="0" echo GTA Radar completed with an issue. See the V6 dashboard in GTA_RADAR_RESULTS.
if /I not "%~1"=="--unattended" pause
exit /b %RESULT%