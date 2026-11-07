@echo off
setlocal
cd /d "%~dp0"
title GTA Radar - Industrial Equipment Evidence Pilot
echo.
echo GTA Radar - Industrial Equipment Pilot (MANUAL REVIEW ONLY)
echo Uses existing Radar database read-only. Maximum 5 ERO notice requests.
echo Checks ERO robots.txt, makes no paid AI calls, and never sends outreach.
echo Scheduled daily Radar collection is NOT changed by this pilot.
echo.
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "%~dp0gta_industrial_equipment_run.py" --limit 5 %*
) else (
  python "%~dp0gta_industrial_equipment_run.py" --limit 5 %*
)
set "STATUS=%errorlevel%"
echo.
if not "%STATUS%"=="0" echo Pilot could not finish; inspect the diagnostic output above.
echo See GTA_RADAR_RESULTS\INDUSTRIAL_PILOT for CSV, HTML and status JSON.
if /I not "%~1"=="--unattended" pause
exit /b %STATUS%
