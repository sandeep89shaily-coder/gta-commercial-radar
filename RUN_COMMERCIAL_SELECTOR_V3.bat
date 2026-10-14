@echo off
cd /d "%~dp0"
python -u commercial_selector_v3.py
if errorlevel 1 (
 echo Report failed. Please send screenshot.
 pause
 exit /b 1
)
start "" "data\commercial_candidates_v3.html"
pause
