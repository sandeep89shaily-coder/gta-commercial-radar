@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "RESULTS=%USERPROFILE%\Desktop\new data\GTA_RADAR_RESULTS"
if not "%RADAR_RESULTS%"=="" set "RESULTS=%RADAR_RESULTS%"
if not exist "%RESULTS%\GTA_RADAR_INVESTMENT_DISCOVERY" (
  echo ERROR: Generic investment discovery report not found.
  exit /b 1
)
if /I "%~1"=="PAID" (
  echo Investigating public business contact people, phones, and emails.
  py -3 gta_contact_intelligence.py --results "%RESULTS%" --project-name "Ace Brampton" --city Brampton --paid
) else (
  echo Free preflight: identifies source-backed companies; makes no paid API calls.
  py -3 gta_contact_intelligence.py --results "%RESULTS%" --project-name "Ace Brampton" --city Brampton
)
if errorlevel 1 exit /b 1
echo Contact dossier in "%RESULTS%\GTA_RADAR_CONTACT_INTELLIGENCE".
echo Integrated early-investment worklist in "%RESULTS%\GTA_RADAR_EARLY_INVESTMENT_LEADS.csv".
endlocal
