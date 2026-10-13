@echo off
cd /d "%~dp0"
echo Preparing ALL qualifying commercial opportunities from collected data...
python -u commercial_selection_v2.py
if errorlevel 1 (
 echo Selection failed. Please send a screenshot.
 pause
 exit /b 1
)
if exist "data\commercial_candidates_dashboard.html" start "" "data\commercial_candidates_dashboard.html"
echo No DeepSeek calls or charges. Original collectors and databases unchanged.
pause
