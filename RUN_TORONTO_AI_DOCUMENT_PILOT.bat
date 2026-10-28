@echo off
setlocal
title GTA Radar - Toronto AI Document Review
cd /d "%~dp0"
set "AUDIT=%~dp0TORONTO_VERIFIED_REPORTS\VERIFIED_REPORT_FETCH_AUDIT.csv"
set "OUT=%~dp0TORONTO_AI_REVIEW"
set "RESULTS=%USERPROFILE%\Desktop\new data\GTA_RADAR_RESULTS"
if not exist "%RESULTS%\" set "RESULTS=%USERPROFILE%\OneDrive\Desktop\new data\GTA_RADAR_RESULTS"
echo.
echo GTA Radar: verify previously downloaded PDFs and review with DeepSeek.
echo Live paid analysis requires explicit confirmation; no V8 pipeline modification.
echo.
if not exist "%AUDIT%" (
 echo ERROR: Cannot find the 4-PDF pilot audit:
 echo "%AUDIT%"
 echo First run RUN_TORONTO_VERIFIED_REPORTS.bat in this SAME extracted folder.
 pause
 exit /b 1
)
if not exist "%RESULTS%\" (
 echo ERROR: Cannot find your existing GTA_RADAR_RESULTS directory.
 echo No separate paid AI ledger will be created.
 pause
 exit /b 1
)
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (set "PY=py -3") else (set "PY=python")
%PY% -c "import requests,pypdf" >nul 2>nul
if errorlevel 1 (
 echo ERROR: Python dependencies missing. Run py -3 -m pip install -r requirements.txt
 pause
 exit /b 1
)
echo Stage 1: offline checksum preflight, no paid AI calls.
%PY% toronto_ai_document_batch.py --audit "%AUDIT%" --out "%OUT%" --results "%RESULTS%" --limit 4
if errorlevel 1 (
 echo ERROR: Preflight failed. No paid AI requests attempted.
 pause
 exit /b 1
)
echo.
echo Results in TORONTO_AI_REVIEW. A paid run will use your existing V8 DeepSeek
echo key and shared daily budget ledger, analyzing up to four already captured PDFs.
echo The claims stay REVIEW ONLY, and no confirmed leads will be published.
choice /C YN /N /M "Authorize up to 4 budget-limited DeepSeek analyses? [Y/N]: "
if errorlevel 2 (
 echo No paid AI call requested.
 pause
 exit /b 0
)
if errorlevel 1 (
 %PY% toronto_ai_document_batch.py --audit "%AUDIT%" --out "%OUT%" --results "%RESULTS%" --limit 4 --paid
)
echo.
echo Review TORONTO_AI_REVIEW\TORONTO_AI_DOCUMENT_BATCH_AUDIT.csv
pause
