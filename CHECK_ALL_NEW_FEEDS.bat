@echo off
cd /d "%~dp0"
echo Checking all staged Southern Ontario ArcGIS feeds without touching your database...
python audit_batch.py
if errorlevel 1 (
 echo Some sources are blocked. See SOUTHERN_ONTARIO_LIVE_AUDIT.csv
) else (
 echo Audit completed. See SOUTHERN_ONTARIO_LIVE_AUDIT.csv
)
pause
