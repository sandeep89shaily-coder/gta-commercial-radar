@echo off
cd /d "%~dp0"
py -3 regional_pipeline.py
if errorlevel 1 python regional_pipeline.py
start "" "SOUTHERN_ONTARIO_LIVE_AUDIT.html"
echo All regional checks completed. No database was changed.
pause
