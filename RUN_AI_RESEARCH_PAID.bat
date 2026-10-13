@echo off
setlocal
cd /d "%~dp0"
echo ==============================================
echo GTA COMMERCIAL RADAR - DEEPSEEK RESEARCH
echo ==============================================
echo.
echo Current configured daily budget: USD 1.00.
echo Research up to 20 candidates with up to 5 searches, 5 webpages and 5 AI rounds per candidate.
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
