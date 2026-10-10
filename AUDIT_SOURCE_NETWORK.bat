@echo off
cd /d "%~dp0"
py -3 source_network.py init
py -3 source_network.py status
pause
