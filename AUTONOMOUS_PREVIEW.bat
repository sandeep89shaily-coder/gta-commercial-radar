@echo off
cd /d "%~dp0"
python autonomous_investigator.py --limit 10 --dry-run
pause
