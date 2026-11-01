@echo off
setlocal
cd /d "%~dp0"
title GTA Radar - Optional Google Research Pilot (10 projects)
echo.
echo GOOGLE PILOT -- DRY RUN ONLY (NO CHARGES)
echo Your existing DeepSeek daily collection is unchanged.
echo.
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "%~dp0gta_google_grounding_pilot.py" %*
) else (
  python "%~dp0gta_google_grounding_pilot.py" %*
)
set "RESULT=%errorlevel%"
echo.
echo To authorize live Google calls after connecting your API key, open
echo PowerShell in this folder and run:
echo   py -3 gta_google_grounding_pilot.py --paid
echo.
if /I not "%~1"=="--unattended" pause
exit /b %RESULT%
