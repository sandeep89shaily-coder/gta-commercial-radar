@echo off
cd /d "%~dp0"
python ai_investigator.py --dry-run --limit 10
pause
