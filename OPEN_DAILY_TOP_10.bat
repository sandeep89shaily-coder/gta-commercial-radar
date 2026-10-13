@echo off
cd /d "%~dp0"
echo Creating the daily 10 best research candidates from existing collected data...
python -u daily_top_ten.py
if errorlevel 1 (
 echo Daily review failed. Please send a screenshot.
 pause
 exit /b 1
)
if exist "data\daily_top_10_dashboard.html" start "" "data\daily_top_10_dashboard.html"
echo Finished. No DeepSeek API calls or charges.
pause
