@echo off
cd /d "%~dp0"
python business_discovery.py run
if errorlevel 1 echo Some sources failed. See data\business_source_status.csv
echo.
echo Open data\business_dashboard.html for results.
pause
