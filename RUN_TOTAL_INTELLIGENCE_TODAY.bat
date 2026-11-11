@echo off
setlocal EnableExtensions
cd /d "%~dp0"
rem Current canonical manual full Radar release launcher (not Monday-only).
call "%~dp0RUN_GTA_RADAR_TODAY.bat" %*
exit /b %ERRORLEVEL%
