@echo off
setlocal EnableExtensions
title GTA Radar - Unified Intelligence
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (set "PY=py -3") else (set "PY=python")
set "RESULTS=%USERPROFILE%\Desktop\new data\GTA_RADAR_RESULTS"
if not exist "%RESULTS%\" set "RESULTS=%USERPROFILE%\OneDrive\Desktop\new data\GTA_RADAR_RESULTS"
if not exist "%RESULTS%\" (
 echo Existing results folder not located. No data changed.
 pause
 exit /b 1
)
set "OUT=%~dp0AI_PROJECT_REVIEW_V2"
echo Inspecting the shared DeepSeek ledger...
%PY% gta_deepseek_budget_diagnostic.py --results "%RESULTS%" --out "%OUT%\DEEPSEEK_BUDGET_DIAGNOSTIC.json"
if errorlevel 1 goto fail
if exist "%RESULTS%\GTA_RADAR_V8_PENDING_QUEUE.csv" (
 %PY% gta_discovery_tracking.py --queue "%RESULTS%\GTA_RADAR_V8_PENDING_QUEUE.csv" --folder "%RESULTS%"
)
echo Identifying project sources and budget...
%PY% gta_execute_ai_project_research.py --results "%RESULTS%" --out "%OUT%"
if errorlevel 1 goto fail
choice /C YN /N /M "Run up to three paid AI investigations (shared US$0.49 daily cap)? [Y/N]: "
if errorlevel 2 goto report
%PY% gta_execute_ai_project_research.py --results "%RESULTS%" --out "%OUT%" --paid --max-projects 3
if errorlevel 1 goto fail
:report
%PY% gta_integrated_buyer_investigation.py --folder "%OUT%" --results "%RESULTS%"
if errorlevel 1 goto fail
%PY% gta_commercial_review_html.py --folder "%OUT%"
if errorlevel 1 goto fail
if exist "%~dp0AI_PROJECT_REVIEW\AI_PROJECT_RESEARCH_MANIFEST.json" (
 %PY% gta_ai_quality_comparison.py --before "%~dp0AI_PROJECT_REVIEW" --after "%OUT%" --out "%OUT%\AI_QUALITY_COMPARISON.json"
)
%PY% gta_release_acceptance.py --folder "%OUT%" --baseline "%~dp0AI_PROJECT_REVIEW"
if errorlevel 1 goto fail
start "" "%OUT%\COMMERCIAL_REVIEW.html"
echo Review created in "%OUT%".
goto done
:fail
echo ERROR: Workflow stopped. See the output and diagnostic files. Existing database untouched.
:done
pause
