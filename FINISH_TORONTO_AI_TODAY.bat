@echo off
setlocal
title GTA Radar - Same Day AI Recovery (One Report)
cd /d "%~dp0"
set "RESULTS=%USERPROFILE%\Desktop\new data\GTA_RADAR_RESULTS"
if not exist "%RESULTS%\" set "RESULTS=%USERPROFILE%\OneDrive\Desktop\new data\GTA_RADAR_RESULTS"
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (set "PY=py -3") else (set "PY=python")
echo Checking existing PDFs and ALL previous DeepSeek reservations.
%PY% toronto_ai_same_day_recovery.py --results "%RESULTS%"
if errorlevel 1 goto fail
echo.
echo Previous UNKNOWN reservations will be retained and counted in the daily limit.
echo This will authorize ONE additional paid attempt TODAY, if the existing budget allows.
choice /C YN /N /M "Authorize one DeepSeek request? [Y/N]: "
if errorlevel 2 goto done
%PY% toronto_ai_same_day_recovery.py --results "%RESULTS%" --paid
if errorlevel 1 goto fail
echo.
echo If successful, results saved under the earlier PDF folder:
echo TORONTO_AI_SAME_DAY_RECOVERY\RECOVERY_RESULT.json
goto done
:fail
echo Encountered error. No automatic retry.
:done
pause
