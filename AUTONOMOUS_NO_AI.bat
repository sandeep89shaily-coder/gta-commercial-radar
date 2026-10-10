@echo off
cd /d "%~dp0"
python autonomous_investigator.py --limit 10 --max-searches 30 --max-pages 20
pause
