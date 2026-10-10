@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (py -3 peel_pilot.py) else (python peel_pilot.py)
echo.
echo Peel reports saved under data. Existing Radar data unchanged.
pause
