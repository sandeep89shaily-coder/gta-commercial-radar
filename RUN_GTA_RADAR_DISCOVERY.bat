@echo off
setlocal
cd /d "%~dp0"
title GTA Radar - New Projects + Initial DeepSeek Contact Searches
echo Running live project collection, initial DeepSeek source queries,
echo and public business contact research only.
echo You will independently verify projects, owners and suppliers later.
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "%~dp0gta_discovery_run.py" %*
) else (
  python "%~dp0gta_discovery_run.py" %*
)
set "RESULT=%errorlevel%"
echo.
if not "%RESULT%"=="0" echo Discovery run needs review; see GTA_RADAR_DISCOVERY_RUN_STATUS.json.
echo Results are in GTA_RADAR_RESULTS as dated GTA_RADAR_PROJECTS_TO_VERIFY_*.csv/html files.
if /I not "%~1"=="--unattended" pause
exit /b %RESULT%
