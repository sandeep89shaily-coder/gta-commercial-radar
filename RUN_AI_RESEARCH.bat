@echo off
setlocal
cd /d "%~dp0"
echo ==============================================
echo GTA COMMERCIAL RADAR - DEEPSEEK RESEARCH CHECK
echo ==============================================
echo.
echo This is a SAFE DRY RUN. No AI charges will be made.
echo The research agent will identify the first three project candidates.
echo.
python deepseek_research_agent.py
echo.
echo No paid requests were made by this launcher.
pause
