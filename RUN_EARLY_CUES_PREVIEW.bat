@echo off
setlocal
cd /d "%~dp0"
title GTA RADAR - Early Cue Preview (Manual, FREE)
echo GTA RADAR EARLY CUE PILOT - REVIEW ONLY
echo This does NOT launch V8, scheduler or DeepSeek.
echo ----------------------------------------
if not exist "early_cue_watch.py" (
  echo ERROR: early_cue_watch.py is not in this folder.
  echo Download the latest pilot branch before running.
  pause
  exit /b 1
)
where py >nul 2>&1
if not errorlevel 1 (
  py -3 early_cue_watch.py --data-dir data --output-dir GTA_RADAR_RESULTS
) else (
  where python >nul 2>&1
  if errorlevel 1 (
    echo ERROR: Python not found. Use your existing GTA Radar Python installation.
    pause
    exit /b 1
  )
  python early_cue_watch.py --data-dir data --output-dir GTA_RADAR_RESULTS
)
set "ERR=%ERRORLEVEL%"
echo ----------------------------------------
echo Results: GTA_RADAR_RESULTS\EARLY_CUES_SOURCE_STATUS.csv
echo           GTA_RADAR_RESULTS\EARLY_CUES_RESEARCH_QUEUE.csv
echo No AI called; V8 untouched. A new baseline produces zero NEW events.
if not "%ERR%"=="0" echo WARNING: one or more pilot sources FAILED. Do not interpret as zero opportunities.
pause
exit /b %ERR%
