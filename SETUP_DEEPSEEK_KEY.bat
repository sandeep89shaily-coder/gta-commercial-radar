@echo off
cd /d "%~dp0"
echo ===========================================
echo GTA Commercial Radar - DeepSeek API Key
echo ===========================================
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_deepseek_key.ps1"
echo.
pause
