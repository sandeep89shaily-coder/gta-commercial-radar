@echo off
setlocal
cd /d "%~dp0"
echo ==============================================
echo GTA COMMERCIAL RADAR - DEEPSEEK RESEARCH
echo ==============================================
echo.
echo Daily API budget: USD 1.00. This is a deep two-project pilot.
echo Deep research on only 2 candidates. Up to 20 search and webpage actions each, within USD 1 per day.
echo This run requires your authorization.
choice /C YN /M "Start paid DeepSeek research"
if errorlevel 2 goto END
echo Starting investigator. The console will STAY OPEN, including on errors.
echo.
cmd /k "python -u deepseek_research_agent.py --confirm-paid"
:END
echo.
echo No further actions pending.
pause
