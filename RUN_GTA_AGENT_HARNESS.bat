@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title GTA Radar - Evidence-First AI Harness
echo.
echo GTA RADAR AI HARNESS
echo Default: free planning and evidence audit only. No AI charges.
echo Use --paid only if you explicitly authorize DeepSeek charges.
echo Shared daily limit remains US$0.25 across ALL Radar DeepSeek stages.
echo.
where py >nul 2>nul
if not errorlevel 1 (
    py -3 "%~dp0gta_agent_harness.py" %*
) else (
    python "%~dp0gta_agent_harness.py" %*
)
set "CODE=%ERRORLEVEL%"
echo.
if "%CODE%"=="0" (
    echo Harness report: Desktop\new data\GTA_RADAR_RESULTS\AGENT_HARNESS_REVIEW\AI_HARNESS_STATUS.json
    echo This is REVIEW ONLY. It does NOT create verified or sale-ready leads.
) else (
    echo Harness stopped safely. Check AI_HARNESS_STATUS.json if the output folder exists.
)
pause
exit /b %CODE%
