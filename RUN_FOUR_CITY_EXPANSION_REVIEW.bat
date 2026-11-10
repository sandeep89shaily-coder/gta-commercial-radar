@echo off
setlocal
cd /d "%~dp0"
title GTA Radar - Four City Source Readiness
echo.
echo GTA Radar - Controlled expansion readiness (manual only)
echo This reads EXISTING GGH collector status; no municipal fetch or AI spend.
echo No collector, database, scheduling, or sales changes.
echo.
if "%~1"=="" (
  echo Usage: RUN_FOUR_CITY_EXPANSION_REVIEW.bat "C:\path\to\GTA_RADAR_RESULTS"
  exit /b 2
)
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "%~dp0gta_four_city_expansion_gate.py" --results "%~1"
) else (
  python "%~dp0gta_four_city_expansion_gate.py" --results "%~1"
)
set "CODE=%errorlevel%"
if not "%CODE%"=="0" echo Source status audit failed; original files were not intentionally modified.
exit /b %CODE%
