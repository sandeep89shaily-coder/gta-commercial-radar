@echo off
setlocal
cd /d "%~dp0"
title GTA RADAR - Free Public Notice Preview
echo GTA RADAR PUBLIC NOTICES - MANUAL TEST ONLY
echo Sources: Milton posted notices, Pickering development proposals, ERO proposals
echo This does NOT modify V8, use DeepSeek, or schedule automatic runs.
echo --------------------------------------------------
if not exist "early_public_notices.py" (
  echo ERROR: early_public_notices.py missing from this pilot folder.
  echo Open the latest pilot branch ZIP; do not copy files into production V8.
  pause
  exit /b 1
)
where py >nul 2>&1
if not errorlevel 1 (
  py -3 early_public_notices.py --data-dir data --output-dir GTA_RADAR_RESULTS
) else (
  where python >nul 2>&1
  if errorlevel 1 (
    echo ERROR: Python is not installed/available here.
    pause
    exit /b 1
  )
  python early_public_notices.py --data-dir data --output-dir GTA_RADAR_RESULTS
)
set "ERR=%ERRORLEVEL%"
echo --------------------------------------------------
echo Results in GTA_RADAR_RESULTS:
echo    EARLY_PUBLIC_NOTICES_SOURCE_STATUS.csv
echo    EARLY_PUBLIC_NOTICES_RESEARCH_QUEUE.csv
echo    EARLY_PUBLIC_NOTICES_CHANGES_REVIEW_ONLY.csv
echo --------------------------------------------------
if not "%ERR%"=="0" echo CAUTION: at least one source failed. Inspect source status, not zero-lead assumptions.
echo First run always creates source baselines, NOT new commercial leads.
pause
exit /b %ERR%
