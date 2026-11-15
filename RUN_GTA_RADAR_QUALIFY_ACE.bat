@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "RESULTS=%USERPROFILE%\Desktop\new data\GTA_RADAR_RESULTS"
if not "%RADAR_RESULTS%"=="" set "RESULTS=%RADAR_RESULTS%"
if not exist "%RESULTS%\GTA_RADAR_INVESTMENT_DISCOVERY" (
  echo ERROR: Missing blind discovery results. The announcement must be discovered first.
  exit /b 1
)
if /I "%~1"=="PAID" (
  echo Performing paid source-backed ACE Brampton qualification.
  py -3 gta_announcement_commercial_qualification.py --results "%RESULTS%" --project-name "Ace Brampton" --city Brampton --paid --customer-profile "Commercial HVAC, electrical, security, industrial equipment and facility service suppliers in Southern Ontario"
) else (
  echo Free preflight - no DeepSeek calls. Pass PAID to authorize one qualification.
  py -3 gta_announcement_commercial_qualification.py --results "%RESULTS%" --project-name "Ace Brampton" --city Brampton --customer-profile "Commercial HVAC, electrical, security, industrial equipment and facility service suppliers in Southern Ontario"
)
if errorlevel 1 exit /b 1
echo Reports: "%RESULTS%\GTA_RADAR_ANNOUNCEMENT_QUALIFICATION"
echo Early investment worklist: "%RESULTS%\GTA_RADAR_EARLY_INVESTMENT_LEADS.csv"
endlocal
