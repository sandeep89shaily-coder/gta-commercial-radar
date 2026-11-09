@echo off
setlocal
cd /d "%~dp0"
title GTA Radar - Commercial Opening and Facility Activation Pilot
echo.
echo GTA Radar - Commercial Activation Pilot (MANUAL, OFFLINE)
echo Reads the existing Radar database READ ONLY.
echo Does not run collectors, AI, outreach or scheduled workflows.
echo Business licences and building permits DO NOT PROVE an opening.
echo.
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "%~dp0gta_commercial_activation_run.py" %*
) else (
  python "%~dp0gta_commercial_activation_run.py" %*
)
set "CODE=%errorlevel%"
echo.
echo Report: existing new data\GTA_RADAR_RESULTS\COMMERCIAL_ACTIVATION_PILOT
if not "%CODE%"=="0" echo Check the error above; existing Radar data was not modified.
pause
exit /b %CODE%
