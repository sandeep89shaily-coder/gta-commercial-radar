@echo off
cd /d "%~dp0"
if not exist data mkdir data
python daily_radar.py >> "data\daily_run.log" 2>&1
