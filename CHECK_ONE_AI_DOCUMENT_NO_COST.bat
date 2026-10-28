@echo off
setlocal
title GTA Radar - One Document AI Recovery Preflight
cd /d "%~dp0"
set "RESULTS=%USERPROFILE%\Desktop\new data\GTA_RADAR_RESULTS"
if not exist "%RESULTS%\" set "RESULTS=%USERPROFILE%\OneDrive\Desktop\new data\GTA_RADAR_RESULTS"
if not exist "%RESULTS%\" (
 echo ERROR: Existing GTA_RADAR_RESULTS not found. No AI calls made.
 pause
 exit /b 1
)
set "AUDIT=%~dp0TORONTO_VERIFIED_REPORTS\VERIFIED_REPORT_FETCH_AUDIT.csv"
if not exist "%AUDIT%" (
 echo ERROR: No previous captured-PDF audit in this folder.
 echo Keep existing downloaded PDFs. No requests made.
 pause
 exit /b 1
)
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (set "PY=py -3") else (set "PY=python")
echo STEP 1: READ-ONLY LEDGER STATUS. No requests or changes.
%PY% municipal_ai_budget_diagnostic.py --results "%RESULTS%"
if errorlevel 1 (
 echo Diagnostic failed. No AI calls made.
 pause
 exit /b 1
)
echo.
echo STEP 2: CHECKSUMS FOR ONE CAPTURED DOCUMENT. No paid AI.
%PY% toronto_ai_document_batch.py --audit "%AUDIT%" --out "%~dp0TORONTO_AI_ONE_DOCUMENT" --results "%RESULTS%" --limit 1
echo.
echo Existing UNKNOWN holds remain reserved. If duplicate or budget is
echo blocked, this test intentionally does not bypass it.
echo No DeepSeek request was authorized or made by this launcher.
pause
