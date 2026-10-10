@echo off
cd /d "%~dp0"
py -3 source_network.py probe --max-probes 10
pause
