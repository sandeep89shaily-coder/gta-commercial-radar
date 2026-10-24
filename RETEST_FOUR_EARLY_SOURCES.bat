@echo off
setlocal
cd /d "%~dp0"
title GTA RADAR - RETEST FOUR EARLY SOURCES ONLY
echo ================================================================
echo IESO / AJAX / BRAMPTON PDC / BURLINGTON
echo Manual only. Does NOT start V8, scheduler, DeepSeek or outreach.
echo Existing early-only data files are kept for first-seen history.
echo ================================================================
where py >nul 2>&1
if not errorlevel 1 (
  set "PY=py -3"
) else (
  where python >nul 2>&1
  if errorlevel 1 goto no_python
  set "PY=python"
)
if not exist GTA_RADAR_RESULTS mkdir GTA_RADAR_RESULTS
echo.
echo [1/4] Official IESO connection application JSON
%PY% early_cue_watch.py --source ieso_connections --data-dir data --output-dir GTA_RADAR_RESULTS
set "F1=%ERRORLEVEL%"
echo.
echo [2/4] Official Ajax preconsultation and active planning GIS
%PY% early_ajax_watch.py --data-dir data --output-dir GTA_RADAR_RESULTS
set "F2=%ERRORLEVEL%"
echo.
echo [3/4] Brampton eSCRIBE planning committee (calendar-only if agenda JS inaccessible)
%PY% early_discovery_watch.py --source brampton_planning_agendas --data-dir data --output-dir GTA_RADAR_RESULTS
set "F3=%ERRORLEVEL%"
echo.
echo [4/4] Burlington linked ward projects (publisher may block individual pages)
%PY% early_discovery_watch.py --source burlington_ward_discovery --data-dir data --output-dir GTA_RADAR_RESULTS
set "F4=%ERRORLEVEL%"
echo.
echo ================= SOURCE RESULT =================
echo IESO exit=%F1%  Ajax exit=%F2%  Brampton exit=%F3%  Burlington exit=%F4%
echo STATUS reports in GTA_RADAR_RESULTS:
echo   EARLY_CUES_SOURCE_STATUS.csv
echo   EARLY_AJAX_SOURCE_STATUS.csv
echo   EARLY_DISCOVERY_SOURCE_STATUS.csv
echo   EARLY_BURLINGTON_BLOCKED_DETAILS.csv (if a detail page blocked)
echo   EARLY_BURLINGTON_PARTIAL_REVIEW.csv (if a detail page blocked)
echo Brampton PARTIAL_CALENDAR_ONLY is not a completed agenda/applications feed.
echo Burlington HTTP 403 is not zero local development.
echo First run of a source is BASELINE, not NEW.
echo Zip and upload the GTA_RADAR_RESULTS folder for further fixes.
echo =================================================
if not "%F1%"=="0" echo REPAIR CHECK: IESO still failing. Share status CSV.
if not "%F2%"=="0" echo REPAIR CHECK: Ajax still failing. Share status CSV.
if not "%F3%"=="0" echo REPAIR CHECK: Brampton calendar fetch failed. Share status CSV.
if not "%F4%"=="0" echo COVERAGE WARNING: Burlington denied access; no bypass attempted.
pause
exit /b 0
:no_python
echo Python not found. Install Python 3 and dependencies from requirements.txt.
pause
exit /b 1
