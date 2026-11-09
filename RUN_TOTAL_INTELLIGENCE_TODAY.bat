@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title GTA Radar - Complete Monday Intelligence Run
echo Running standard collection and all integrated intelligence pilots.
where py >nul 2>nul
if not errorlevel 1 (
 py -3 "%~dp0gta_monday_full_run.py" %*
) else (
 python "%~dp0gta_monday_full_run.py" %*
)
set "CODE=%ERRORLEVEL%"
echo.
if "%CODE%"=="0" (
 echo COMPLETE RADAR RUN FINISHED. Review GTA_RADAR_RESULTS\MONDAY_FULL_RADAR\MONDAY_FULL_RADAR_REPORT.html.
) else (
 echo One or more stages failed. Read GTA_RADAR_RESULTS\MONDAY_FULL_RADAR\MONDAY_FULL_RADAR_STATUS.json and LOGS.
)
pause
exit /b %CODE%
