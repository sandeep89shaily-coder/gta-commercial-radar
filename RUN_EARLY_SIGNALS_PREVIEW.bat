@echo off
setlocal
cd /d "%~dp0"
echo GTA Radar EARLY SIGNALS pilot - review only
echo This does not change V8, run the daily pipeline, or call DeepSeek.
echo.
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 early_signal_watch.py --data-dir "%~dp0data" --output-dir "%~dp0GTA_RADAR_RESULTS"
) else (
    python early_signal_watch.py --data-dir "%~dp0data" --output-dir "%~dp0GTA_RADAR_RESULTS"
)
echo.
if errorlevel 1 (
    echo One or more early-planning sources failed. See EARLY_SIGNALS_SOURCES_STATUS.csv
) else (
    echo Completed review-only collection.
)
echo Results in GTA_RADAR_RESULTS
pause
endlocal
