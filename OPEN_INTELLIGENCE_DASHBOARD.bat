@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
%PY% intelligence_dashboard.py
%PY% production_readiness.py
if exist "data\radar_intelligence_dashboard.html" start "" "data\radar_intelligence_dashboard.html"
echo.
echo This is a read-only report. Source data was not modified.
pause
