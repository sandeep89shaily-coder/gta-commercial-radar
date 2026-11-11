@echo off
setlocal EnableExtensions
cd /d "%~dp0"
rem Legacy shortcut remains supported; current day is determined at runtime.
call "%~dp0RUN_GTA_RADAR_TODAY.bat" %*
exit /b %ERRORLEVEL%
