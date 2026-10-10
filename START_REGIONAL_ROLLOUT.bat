@echo off
cd /d "%~dp0"
echo Southern Ontario -- regional collection on a SAFE COPY of existing data
py -3 regional_activation.py
echo.
echo Send a screenshot of the final summary. Older folders are unchanged.
pause
