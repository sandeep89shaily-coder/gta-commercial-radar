@echo off
setlocal
cd /d "%~dp0"
title GTA Radar Early Signals - Retry Failed Sources
echo EARLY SIGNALS - safe retry of the 3 failed sources
echo Existing V8 and successful baselines will not be changed.
echo.
if not exist "early_signal_watch.py" (
  echo ERROR: Put this file beside RUN_EARLY_SIGNALS_PREVIEW.bat in your extracted pilot folder.
  goto end
)
if not exist "data\early_signals_review.sqlite" (
  echo ERROR: First-run baseline database was not found. Stopping to protect your history.
  goto end
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $u='https://raw.githubusercontent.com/sandeep89shaily-coder/gta-commercial-radar/205f182ff9c9250fce39a3fb50c4c26498947d82/early_signal_watch.py'; $temp='early_signal_watch.download.py'; Invoke-WebRequest -Uri $u -OutFile $temp; if((Get-Item $temp).Length -lt 9000){throw 'Download unexpectedly small'}; if(-not (Select-String -Path $temp -Pattern 'def fetch_batch' -SimpleMatch -Quiet)){throw 'Downloaded file failed verification'}; Copy-Item -Force 'early_signal_watch.py' 'early_signal_watch.before_retry.bak'; Move-Item -Force $temp 'early_signal_watch.py'; Write-Host 'Updated isolated collector successfully.'"
if errorlevel 1 (
  echo ERROR: Download failed. Existing file and data remain unchanged.
  goto end
)
echo.
echo Testing ONLY Brampton pre-consultation, Brampton site plans and Toronto...
echo.
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 early_signal_watch.py --data-dir "%~dp0data" --output-dir "%~dp0GTA_RADAR_RESULTS" --source brampton_preconsultation --source brampton_site_plans --source toronto_development
) else (
  python early_signal_watch.py --data-dir "%~dp0data" --output-dir "%~dp0GTA_RADAR_RESULTS" --source brampton_preconsultation --source brampton_site_plans --source toronto_development
)
echo.
if errorlevel 1 (
  echo One or more sources still failed. Upload the new EARLY_SIGNALS_SOURCES_STATUS.csv.
) else (
  echo All three sources succeeded. Upload EARLY_SIGNALS_SOURCES_STATUS.csv.
)
:end
echo.
pause
endlocal
