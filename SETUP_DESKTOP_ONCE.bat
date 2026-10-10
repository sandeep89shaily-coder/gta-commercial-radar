@echo off
setlocal
cd /d "%~dp0"
title GTA Radar - One Time Desktop Setup
where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
%PY% setup_desktop.py
if errorlevel 1 (
 echo.
 echo Setup needs attention. Your old Radar folders were not changed.
) else (
 echo.
 echo Setup finished. You can close this window.
)
pause
