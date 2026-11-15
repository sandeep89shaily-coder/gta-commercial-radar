@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if "%~1"=="" (
  echo Usage: RUN_GTA_RADAR_COORDINATED.bat RECORD_ID [PAID]
  echo Example: RUN_GTA_RADAR_COORDINATED.bat toronto_development_applications:25249692ESC21CD
  exit /b 2
)
set "RESULTS=%USERPROFILE%\Desktop\new data\GTA_RADAR_RESULTS"
if not "%RADAR_RESULTS%"=="" set "RESULTS=%RADAR_RESULTS%"
if not exist "%RESULTS%\GTA_RADAR_COMMERCIAL_TOP10_ANALYST_REVIEW.csv" (
  echo ERROR: Current Radar Top 10 CSV does not exist under "%RESULTS%".
  exit /b 1
)
if /I "%~2"=="PAID" (
  echo Paid coordinated research is explicitly enabled for exact record: %~1
  py -3 gta_coordinated_investigator.py --results "%RESULTS%" --record-id "%~1" --paid
  if errorlevel 1 exit /b 1
  py -3 gta_commercial_qualification_review.py --results "%RESULTS%"
  if errorlevel 1 exit /b 1
) else (
  echo Free preflight only. To authorize DeepSeek use second argument PAID.
  py -3 gta_coordinated_investigator.py --results "%RESULTS%" --record-id "%~1"
  if errorlevel 1 exit /b 1
)
echo Check GTA_RADAR_COORDINATED_CASES in "%RESULTS%" for JSON and Markdown.
endlocal
