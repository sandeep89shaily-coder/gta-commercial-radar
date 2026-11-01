@echo off
setlocal
title GTA Radar - FREE Buyer and Procurement Test
set "CODE=%~dp0"
set "RESULTS=%CODE%..\GTA_RADAR_RESULTS"
set "REVIEW=%RESULTS%\TOTAL_INTELLIGENCE_REVIEW"
set "PY=python"
where py >nul 2>nul && set "PY=py -3"
if not exist "%RESULTS%" (
  echo ERROR: Expected existing results folder not found:
  echo "%RESULTS%"
  echo Historical files were NOT changed.
  pause
  exit /b 2
)
if not exist "%REVIEW%" mkdir "%REVIEW%"
echo Checking installed GitHub release before running...
%PY% "%CODE%desktop_update.py" --code-dir "%CODE%" --results-dir "%RESULTS%"
if errorlevel 1 (
  echo RELEASE CHECK FAILED. No live source check ran.
  pause
  exit /b 3
)
echo.
echo Checking source-linked purchasing observations. No paid AI calls.
%PY% "%CODE%gta_live_procurement_evidence.py" --results "%RESULTS%" --review "%REVIEW%" --out "%REVIEW%" --limit 30
if errorlevel 1 (
  echo Procurement evidence test failed. See output folder.
  pause
  exit /b 4
)
echo.
echo Preparing buyer follow-up for existing projects...
%PY% "%CODE%gta_buyer_procurement_batch.py" --results "%RESULTS%" --review "%REVIEW%" --out "%REVIEW%" --top 10
if errorlevel 1 (
  echo Buyer follow-up report failed.
  pause
  exit /b 5
)
echo.
echo FREE TEST COMPLETE. Check:
echo "%REVIEW%"
echo Any UNKNOWN status remains UNKNOWN. Zero verified packages may be the correct result.
pause
endlocal
