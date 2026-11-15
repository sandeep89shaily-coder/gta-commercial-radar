@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "RESULTS=%USERPROFILE%\Desktop\new data\GTA_RADAR_RESULTS"
if not "%RADAR_RESULTS%"=="" set "RESULTS=%RADAR_RESULTS%"
if not exist "%RESULTS%\GTA_RADAR_COMMERCIAL_TOP10_ANALYST_REVIEW.csv" (
  echo Radar Top 10 CSV not found in "%RESULTS%".
  echo Run the ordinary manual Radar collector first and check the results folder.
  pause
  exit /b 1
)
set "COUNT=2"
if not "%~1"=="" set "COUNT=%~1"
if not "%COUNT%"=="1" if not "%COUNT%"=="2" if not "%COUNT%"=="10" (
  echo Usage: RUN_GTA_RADAR_AI_ALL_TEN.bat [1 ^| 2 ^| 10]
  exit /b 2
)
echo GTA Radar: running all ten AI capabilities across %COUNT% shortlisted projects.
echo Original source evidence remains required. No automatic outreach.
py -3 gta_commercial_qualification_review.py --results "%RESULTS%" --paid-ai-ten --ai-limit %COUNT%
if errorlevel 1 (
  echo Radar ten-capability run encountered an error; checkpoints are retained.
  pause
  exit /b 1
)
echo Dossiers and briefs saved in "%RESULTS%".
pause
endlocal
