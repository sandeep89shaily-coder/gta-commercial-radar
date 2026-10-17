@echo off
cd /d "%~dp0"
echo Running commercial review V4 against existing data. No paid AI.
python -u commercial_selector_v4.py
if errorlevel 1 (
 echo V4 review failed. The existing database has not been changed.
 pause
 exit /b 1
)
if exist "data\commercial_candidates_v4.html" start "" "data\commercial_candidates_v4.html"
echo V4 candidates are research-only, not verified sales leads.
pause
