@echo off
setlocal
cd /d "%~dp0"
echo GTA Commercial Radar - Autonomous Investigator v0.12
echo.
echo You need a Brave Search API key. It will be used only for this run.
if not defined BRAVE_SEARCH_API_KEY set /p BRAVE_SEARCH_API_KEY=Brave Search API key: 
if not defined BRAVE_SEARCH_API_KEY (
 echo Missing search key. Nothing was searched.
 pause
 exit /b 2
)
if not exist "data\lead_research_REVIEW_ONLY.csv" (
 echo Preparing candidate research queue...
 python lead_research.py
 if errorlevel 1 (echo Could not prepare lead queue. & pause & exit /b 1)
)
choice /C YN /M "Use OpenAI AI analysis too (requires a separate API key)"
if errorlevel 2 goto NOAI
if not defined OPENAI_API_KEY set /p OPENAI_API_KEY=OpenAI API key: 
if not defined OPENAI_API_KEY goto NOAI
python autonomous_investigator.py --limit 10 --max-searches 30 --max-pages 20 --ai
goto END
:NOAI
python autonomous_investigator.py --limit 10 --max-searches 30 --max-pages 20
:END
echo.
echo Check data\autonomous_investigations_REVIEW_ONLY.csv
pause
