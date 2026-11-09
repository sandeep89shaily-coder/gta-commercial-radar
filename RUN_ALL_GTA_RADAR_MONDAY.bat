@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title GTA Commercial Radar - Monday Full Run
echo.
echo GTA Commercial Radar - full manual collection and all four intelligence pilots
echo Existing official collection runs once, then separate review-only outputs.
echo Industrial ERO fetch is capped at ten notices and respects robots.txt.
echo AI harness runs FREE preflight only; normal Radar owns the shared AI budget.
echo No outreach and no new scheduled tasks.
echo.
where py >nul 2>nul
if not errorlevel 1 (
 py -3 "%~dp0gta_monday_full_run.py" %*
) else (
 python "%~dp0gta_monday_full_run.py" %*
)
set "CODE=%ERRORLEVEL%"
echo.
echo Review GTA_RADAR_RESULTS\MONDAY_FULL_RADAR\MONDAY_FULL_RADAR_REPORT.html
if not "%CODE%"=="0" echo One or more stages failed. Read MONDAY_FULL_RADAR_STATUS.json and LOGS.
pause
exit /b %CODE%
