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
if not exist "early_ajax_watch.py" goto missing
if not exist "early_oakville_watch.py" goto missing
if not exist "early_hamilton_watch.py" goto missing
if not exist "hamilton_industrial_triage.py" goto missing
if not exist "hamilton_company_evidence_export.py" goto missing
if not exist "early_buyer_evidence.py" goto missing
if not exist "early_leadtime_evidence.py" goto missing
if not exist "toronto_aic_email_import.py" goto missing
if not exist "early_markham_circulation.py" goto missing
if not exist "early_product_evidence_preview.py" goto missing
if not exist "early_project_scope_audit.py" goto missing
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
echo [1/17] IESO connections and known Burlington project pages
%PYCMD% early_cue_watch.py --data-dir data --output-dir GTA_RADAR_RESULTS
set "FAIL1=%ERRORLEVEL%"
echo [2/17] Milton, Pickering, and ERO public proposals
%PYCMD% early_public_notices.py --data-dir data --output-dir GTA_RADAR_RESULTS
set "FAIL2=%ERRORLEVEL%"
echo [3/17] Burlington ward project discovery and Brampton council agendas
%PYCMD% early_discovery_watch.py --data-dir data --output-dir GTA_RADAR_RESULTS
set "FAIL3=%ERRORLEVEL%"
echo [4/17] Ontario public investment news and federal open tenders
%PYCMD% early_investment_tenders.py --data-dir data --output-dir GTA_RADAR_RESULTS
set "FAIL4=%ERRORLEVEL%"
echo [5/17] Ajax public planning application index
%PYCMD% early_ajax_watch.py --data-dir data --output-dir GTA_RADAR_RESULTS
set "FAILAJAX=%ERRORLEVEL%"
echo [6/17] Optional Toronto AIC email notices (NO inbox access)
%PYCMD% toronto_aic_email_import.py --eml-folder data\toronto_aic_eml --data-dir data --output-dir GTA_RADAR_RESULTS
set "FAILAIC=%ERRORLEVEL%"
echo [7/17] Oakville seven-ward published development index
%PYCMD% early_oakville_watch.py --data-dir data --output-dir GTA_RADAR_RESULTS
set "FAILOAK=%ERRORLEVEL%"
echo [8/17] Hamilton official planning GIS and dated development notices
%PYCMD% early_hamilton_watch.py --data-dir data --output-dir GTA_RADAR_RESULTS --max-notice-details 20
set "FAILHAM=%ERRORLEVEL%"
echo [9/17] Rank Hamilton industrial planning records and match actual city notice files
%PYCMD% hamilton_industrial_triage.py --database data\early_hamilton_review.sqlite --output-dir GTA_RADAR_RESULTS --limit 200
set "FAILHAMTRIAGE=%ERRORLEVEL%"
echo [10/17] Export 12 sourced Hamilton business-investigation cases (not sale ready)
%PYCMD% hamilton_company_evidence_export.py --output-dir GTA_RADAR_RESULTS
set "FAILHAMRESEARCH=%ERRORLEVEL%"
echo [11/17] Audit exact Hamilton project scope versus withdrawn approvals and existing permits
%PYCMD% early_project_scope_audit.py --output-dir GTA_RADAR_RESULTS
set "FAILSCOPE=%ERRORLEVEL%"
echo [12/17] Monitor Markham official circulated development-application PDF reports
%PYCMD% early_markham_circulation.py --data-dir data --output-dir GTA_RADAR_RESULTS
set "FAILMARKHAM=%ERRORLEVEL%"
echo [13/17] Compare all available separate early-source databases (read-only)
%PYCMD% early_evidence_match.py --data-dir data --output-dir GTA_RADAR_RESULTS
set "FAIL5=%ERRORLEVEL%"
echo [14/17] Preserve buyer/procurement evidence worksheets; evidence-gate all leads
%PYCMD% early_buyer_evidence.py --output-dir GTA_RADAR_RESULTS
set "FAILBUYER=%ERRORLEVEL%"
echo [15/17] Generate internal evidence dossier product sample (NOT marketing)
%PYCMD% early_product_evidence_preview.py --output-dir GTA_RADAR_RESULTS
set "FAILPREVIEW=%ERRORLEVEL%"
echo [16/17] Compare verified human-entered public posting dates to later public stages
%PYCMD% early_leadtime_evidence.py --output-dir GTA_RADAR_RESULTS
set "FAILTIME=%ERRORLEVEL%"
echo [17/17] Prepare one source health summary and research-only shortlist
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
if not "%FAILAJAX%"=="0" goto failed
if not "%FAILOAK%"=="0" goto failed
if not "%FAILHAM%"=="0" goto failed
if not "%FAILHAMTRIAGE%"=="0" goto failed
if not "%FAILHAMRESEARCH%"=="0" goto failed
if not "%FAILSCOPE%"=="0" goto failed
if not "%FAILMARKHAM%"=="0" goto failed
if not "%FAILPREVIEW%"=="0" goto failed
if not "%FAILBUYER%"=="0" goto failed
if not "%FAILTIME%"=="0" goto failed
if not "%FAILAIC%"=="0" goto failed
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
