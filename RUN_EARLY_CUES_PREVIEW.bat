@echo off
setlocal
cd /d "%~dp0"
title GTA RADAR - Free Early Intelligence Manual Preview
echo ===============================================================
echo GTA RADAR EARLY INTELLIGENCE - ONE MANUAL TEST
echo No V8 / scheduler / DeepSeek / paid provider / outreach.
echo Keeps historical first-seen data in isolated SQLite databases.
echo Original 7 GIS sources are NOT re-collected here.
echo ===============================================================
if not exist "early_cue_watch.py" goto missing
if not exist "early_public_notices.py" goto missing
if not exist "early_discovery_watch.py" goto missing
if not exist "early_investment_tenders.py" goto missing
if not exist "early_evidence_match.py" goto missing
if not exist "early_pilot_summary.py" goto missing
where py >nul 2>&1
if not errorlevel 1 (
  set "PYCMD=py -3"
) else (
  where python >nul 2>&1
  if errorlevel 1 goto py_missing
  set "PYCMD=python"
)
if not exist GTA_RADAR_RESULTS mkdir GTA_RADAR_RESULTS
echo [1/6] IESO connections and known Burlington project pages
%PYCMD% early_cue_watch.py --data-dir data --output-dir GTA_RADAR_RESULTS
set "FAIL1=%ERRORLEVEL%"
echo [2/6] Milton, Pickering, and ERO public proposals
%PYCMD% early_public_notices.py --data-dir data --output-dir GTA_RADAR_RESULTS
set "FAIL2=%ERRORLEVEL%"
echo [3/6] Burlington ward project discovery and Brampton council agendas
%PYCMD% early_discovery_watch.py --data-dir data --output-dir GTA_RADAR_RESULTS
set "FAIL3=%ERRORLEVEL%"
echo [4/6] Ontario public investment news and federal open tenders
%PYCMD% early_investment_tenders.py --data-dir data --output-dir GTA_RADAR_RESULTS
set "FAIL4=%ERRORLEVEL%"
echo [5/6] Compare all available separate early-source databases (read-only)
%PYCMD% early_evidence_match.py --data-dir data --output-dir GTA_RADAR_RESULTS
set "FAIL5=%ERRORLEVEL%"
echo [6/6] Prepare one source health summary and research-only shortlist
%PYCMD% early_pilot_summary.py --output-dir GTA_RADAR_RESULTS
set "FAIL6=%ERRORLEVEL%"
echo ===============================================================
echo OPEN: GTA_RADAR_RESULTS\EARLY_PILOT_RUN_SUMMARY.txt
echo ALSO: GTA_RADAR_RESULTS\EARLY_TOP_RESEARCH_PREVIEW.csv
echo Source failures never mean zero projects; see the summary.
echo First successful run establishes baseline, not NEW commercial leads.
echo ===============================================================
if not "%FAIL1%"=="0" goto failed
if not "%FAIL2%"=="0" goto failed
if not "%FAIL3%"=="0" goto failed
if not "%FAIL4%"=="0" goto failed
if not "%FAIL5%"=="0" goto failed
if not "%FAIL6%"=="0" goto failed
echo All test commands finished without source errors. Review coverage limitations.
pause
exit /b 0
:missing
echo ERROR: some pilot scripts missing. Use the newest early-signals pilot branch.
pause
exit /b 1
:py_missing
echo ERROR: Python not found. Use your existing GTA Radar Python environment.
pause
exit /b 1
:failed
echo CAUTION: one or more sources / reports failed. History retained.
echo Inspect the status and errors before treating results as trustworthy.
pause
exit /b 1
