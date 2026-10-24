@echo off
setlocal
cd /d "%~dp0"
title GTA RADAR - New Early Cue Sources [Manual Only]
echo GTA RADAR - TEST ALL NEW EARLY-CUE SOURCES
echo Sources: IESO, Burlington, Milton, Pickering and ERO proposals.
echo NOTE: original 7 GIS sources stay untouched.
echo V8 untouched. No scheduler. No paid AI.
echo -------------------------------------------------
if not exist "early_cue_watch.py" goto missing
if not exist "early_public_notices.py" goto missing
where py >nul 2>&1
if not errorlevel 1 (
  set "PYCMD=py -3"
) else (
  where python >nul 2>&1
  if errorlevel 1 goto py_missing
  set "PYCMD=python"
)
echo.
echo [1/2] IESO + Burlington pre-application cues
%PYCMD% early_cue_watch.py --data-dir data --output-dir GTA_RADAR_RESULTS
set "ERR1=%ERRORLEVEL%"
echo.
echo [2/2] Milton + Pickering + ERO proposal notices
%PYCMD% early_public_notices.py --data-dir data --output-dir GTA_RADAR_RESULTS
set "ERR2=%ERRORLEVEL%"
echo.
echo -------------------------------------------------
echo Review statuses in GTA_RADAR_RESULTS:
echo   EARLY_CUES_SOURCE_STATUS.csv
echo   EARLY_PUBLIC_NOTICES_SOURCE_STATUS.csv
echo Also see the two RESEARCH_QUEUE.csv files.
echo First successful snapshots are historical baselines, not NEW leads.
if not "%ERR1%"=="0" echo WARNING: IESO/Burlington watcher reported source failures.
if not "%ERR2%"=="0" echo WARNING: Milton/Pickering/ERO watcher reported source failures.
if not "%ERR1%"=="0" goto failed
if not "%ERR2%"=="0" goto failed
echo Two new watcher batches completed; review each source status for coverage caveats.
pause
exit /b 0
:missing
echo ERROR: this folder is missing one of the two pilot Python files.
echo Use the latest pilot branch folder; do not place these in production V8.
pause
exit /b 1
:py_missing
echo ERROR: Python not available on this PC.
pause
exit /b 1
:failed
echo REVIEW NEEDED: one or more collectors failed. Historical database retained.
pause
exit /b 1
