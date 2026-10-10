@echo off
cd /d "%~dp0"
echo GTA Radar v0.8 - first-time safe setup
python setup_business.py
if errorlevel 1 (
  echo Setup needs attention. Your existing database was not overwritten.
  pause
  exit /b 1
)
echo.
echo Starting business-discovery collection. The first federal download may be large.
python business_discovery.py run
if errorlevel 1 echo A source needs review. See data\business_source_status.csv
start "" "data\business_dashboard.html"
pause
