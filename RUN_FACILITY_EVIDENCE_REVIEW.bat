@echo off
setlocal
cd /d "%~dp0"
title GTA Radar - Offline Facility Evidence Review
echo.
echo GTA Radar - Combined Facility Evidence and Commercial Dossier Pilot
echo Manual use only; this does NOT launch the daily collector.
echo Does NOT change Radar database, schedules, DeepSeek budget or outreach.
echo Processing existing historical results ONLY - not proof of new business.
echo.
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "%~dp0gta_facility_review_run.py" %*
) else (
  python "%~dp0gta_facility_review_run.py" %*
)
set "CODE=%errorlevel%"
echo.
echo Output folders:
echo Existing new data\GTA_RADAR_RESULTS\FACILITY_INTELLIGENCE_PILOT
echo Existing new data\GTA_RADAR_RESULTS\FACILITY_DOSSIER_PILOT
if not "%CODE%"=="0" echo Pilot refused or failed. Original Radar files were not intentionally modified.
pause
exit /b %CODE%
