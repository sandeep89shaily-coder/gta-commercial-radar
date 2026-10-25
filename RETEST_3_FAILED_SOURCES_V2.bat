@echo off
setlocal
cd /d "%~dp0"
title GTA RADAR - THREE OFFICIAL SOURCE RETEST V2
echo =========================================================
echo GTA RADAR - VERIFIED SOURCE RETEST V2 (Oct 24)
echo IESO official JSON / Brampton committee / Ajax official GIS
echo Burlington already PASSED: it will NOT be recollected.
echo Does not use V8, DeepSeek, scheduler or sales contacts.
echo =========================================================
if not exist "early_ajax_arcgis.py" goto missing
if not exist "early_cue_watch.py" goto missing
if not exist "early_discovery_watch.py" goto missing
if not exist "early_ajax_watch.py" goto missing
if not exist "diagnose_three_sources.py" goto missing
where py >nul 2>&1
if not errorlevel 1 (
  set "PY=py -3"
) else (
  where python >nul 2>&1
  if errorlevel 1 goto no_python
  set "PY=python"
)
if not exist "GTA_RADAR_RESULTS" mkdir "GTA_RADAR_RESULTS"
echo [1/3] IESO - official publisher JSON
%PY% early_cue_watch.py --source ieso_connections --data-dir data --output-dir GTA_RADAR_RESULTS
set "I=%ERRORLEVEL%"
echo [2/3] Brampton published planning calendar and supported agenda HTML
%PY% early_discovery_watch.py --source brampton_planning_agendas --data-dir data --output-dir GTA_RADAR_RESULTS
set "B=%ERRORLEVEL%"
echo [3/3] Ajax official ArcGIS preconsultation and active planning
%PY% early_ajax_watch.py --data-dir data --output-dir GTA_RADAR_RESULTS
set "A=%ERRORLEVEL%"
echo =========================================================
echo EXIT CODES: IESO=%I% Brampton=%B% Ajax=%A%
echo Detailed official source status and error messages:
%PY% diagnose_three_sources.py --output-dir GTA_RADAR_RESULTS
echo =========================================================
echo If any collector failed, ZIP GTA_RADAR_RESULTS and upload it.
echo HTTP 403 or publisher JS blocking is not zero new opportunities.
echo First successful source collection starts a historical baseline.
echo =========================================================
pause
if not "%I%"=="0" exit /b 1
if not "%B%"=="0" exit /b 1
if not "%A%"=="0" exit /b 1
exit /b 0
:missing
echo ERROR: Pilot folder is missing source modules. Extract the latest repair ZIP into the PILOT directory, not production V8.
pause
exit /b 1
:no_python
echo ERROR: Python was not found.
pause
exit /b 1
