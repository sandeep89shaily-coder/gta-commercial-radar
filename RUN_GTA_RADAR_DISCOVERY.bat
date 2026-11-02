@echo off
setlocal
cd /d "%~dp0"
title GTA Radar - Integrated Daily Construction Intelligence
echo Running the full integrated daily intelligence review:
echo permits, meetings, official municipal PDFs, project and buyer-role
echo research, supplier/procurement source checks and project history.
echo Paid DeepSeek stages share the US$0.25 daily ledger.
echo Project/company/buyer/supplier verification and outreach remain manual.
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "%~dp0gta_discovery_run.py" %*
) else (
  python "%~dp0gta_discovery_run.py" %*
)
set "RESULT=%errorlevel%"
echo.
if not "%RESULT%"=="0" echo One or more stages require review; see GTA_RADAR_DISCOVERY_RUN_STATUS.json.
echo Combined: GTA_RADAR_RESULTS\GTA_RADAR_INTEGRATED_INTELLIGENCE.html
echo Combined CSV: GTA_RADAR_RESULTS\GTA_RADAR_INTEGRATED_INTELLIGENCE.csv
echo Original project review: GTA_RADAR_RESULTS\GTA_RADAR_PROJECTS_TO_VERIFY_*.csv/html
echo Stage health: GTA_RADAR_RESULTS\GTA_RADAR_INTEGRATED_INTELLIGENCE_STATUS.json
if /I not "%~1"=="--unattended" pause
exit /b %RESULT%
