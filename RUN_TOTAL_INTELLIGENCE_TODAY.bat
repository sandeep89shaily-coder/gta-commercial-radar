@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title GTA Radar - Total Intelligence Run
echo Starting one complete intelligence run using your existing Desktop data.
where py >nul 2>nul
if not errorlevel 1 (
 py -3 "%~dp0gta_total_intelligence_run.py" %*
) else (
 python "%~dp0gta_total_intelligence_run.py" %*
)
set "CODE=%ERRORLEVEL%"
echo.
if "%CODE%"=="0" (
 echo TOTAL INTELLIGENCE RUN FINISHED. Review GTA_RADAR_RESULTSTOTAL_INTELLIGENCE_REVIEW.
) else (
 echo One or more stages failed. Read TOTAL_RUN_STATUS.json and stage logs.
)
pause
exit /b %CODE%
