@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "RESULTS=%USERPROFILE%\Desktop\new data\GTA_RADAR_RESULTS"
if not "%RADAR_RESULTS%"=="" set "RESULTS=%RADAR_RESULTS%"
if not exist "%RESULTS%" (
  echo Missing Radar results directory: "%RESULTS%"
  exit /b 1
)
if /I "%~1"=="PAID" (
  echo Running one generic Brampton industrial discovery.
  echo Search terms will not include known company, project, or street names.
  py -3 gta_investment_announcement_discovery.py --results "%RESULTS%" --city Brampton --paid
) else (
  echo Free preflight only. Pass PAID to authorize provider calls.
  py -3 gta_investment_announcement_discovery.py --results "%RESULTS%" --city Brampton
)
if errorlevel 1 exit /b 1
echo Results stored in "%RESULTS%\GTA_RADAR_INVESTMENT_DISCOVERY".
endlocal
