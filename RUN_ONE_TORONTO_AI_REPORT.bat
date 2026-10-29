@echo off
setlocal
title GTA Radar - One-click Toronto AI Review
cd /d "%~dp0"
set "RESULTS=%USERPROFILE%\Desktop\new data\GTA_RADAR_RESULTS"
if not exist "%RESULTS%\" set "RESULTS=%USERPROFILE%\OneDrive\Desktop\new data\GTA_RADAR_RESULTS"
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (set "PY=py -3") else (set "PY=python")
echo ONE-DOCUMENT REAL AI PIPELINE - reuse previous PDFs, no download.
echo.
echo Checking saved file and local budget without AI call...
%PY% toronto_ai_one_click.py --results "%RESULTS%"
if errorlevel 1 goto error
echo.
echo No previous UNKNOWN reservations will be released or retried automatically.
echo If a request was already attempted today it remains blocked.
choice /C YN /N /M "Authorize one budget-limited DeepSeek report analysis, if eligible? [Y/N]: "
if errorlevel 2 goto done
%PY% toronto_ai_one_click.py --results "%RESULTS%" --paid
if errorlevel 1 goto error
echo.
echo If successful, open TORONTO_AI_SINGLE_REPORT\TORONTO_AI_REVIEW.html
echo under the prior extracted folder containing your downloaded PDFs.
goto done
:error
echo Test encountered an error. No automatic retry.
:done
pause
