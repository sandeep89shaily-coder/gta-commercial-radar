@echo off
setlocal
title GTA Radar - AI Project Investigation
cd /d "%~dp0"
where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (set "PY=py -3") else (set "PY=python")
set "RESULTS=%USERPROFILE%\Desktop\new data\GTA_RADAR_RESULTS"
if not exist "%RESULTS%\" set "RESULTS=%USERPROFILE%\OneDrive\Desktop\new data\GTA_RADAR_RESULTS"
if not exist "%RESULTS%\" (
 echo Could not find existing GTA_RADAR_RESULTS shared ledger.
 pause
 exit /b 1
)
echo DeepSeek ledger and execution diagnostic:\n%PY% gta_deepseek_budget_diagnostic.py --results "%RESULTS%" --out "%~dp0DEEPSEEK_BUDGET_DIAGNOSTIC.json"\necho GTA RADAR - ACTUAL DEEPSEEK PROJECT RESEARCH
echo Automatically locating the V8 project queue in existing results folders.
set "OUT=%~dp0AI_PROJECT_REVIEW_V2"
%PY% gta_execute_ai_project_research.py --results "%RESULTS%" --out "%OUT%"
if errorlevel 1 goto fail
echo.
echo The following is a PAID DeepSeek execution, not a preview.
echo Existing shared US dollar daily budget maximum: 0.49.
choice /C YN /N /M "Run DeepSeek research on up to three projects now? [Y/N]: "
if errorlevel 2 goto done
%PY% gta_execute_ai_project_research.py --results "%RESULTS%" --out "%OUT%" --paid --max-projects 3
if errorlevel 1 goto fail
echo Results and source pages saved in "%OUT%".
if exist "%~dp0AI_PROJECT_REVIEW\AI_PROJECT_RESEARCH_MANIFEST.json" (
 %PY% gta_ai_quality_comparison.py --before "%~dp0AI_PROJECT_REVIEW" --after "%OUT%" --out "%OUT%\AI_QUALITY_COMPARISON.json"
)
goto done
:fail
echo Operation failed. No automatic paid retries.
:done
pause
