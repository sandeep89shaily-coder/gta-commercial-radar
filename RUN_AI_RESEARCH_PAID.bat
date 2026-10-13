@echo off
setlocal
cd /d "%~dp0"
echo ==============================================
echo GTA COMMERCIAL RADAR - PAID AI RESEARCH PILOT
echo ==============================================
echo.
echo DeepSeek will search the public web and read permitted pages.
echo Up to 3 research candidates. Daily spending capped by ledger to USD 0.50.
echo Results are research-only, not sale-ready verified leads.
echo.
choice /C YN /M "Authorize DeepSeek API charges within the configured daily budget"
if errorlevel 2 goto END
python deepseek_research_agent.py --confirm-paid
:END
echo.
pause
