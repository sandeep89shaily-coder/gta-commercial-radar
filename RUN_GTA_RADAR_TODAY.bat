@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
if errorlevel 1 (
 echo ERROR: Cannot access the GTA Radar code folder.
 pause
 exit /b 3
)
title GTA Commercial Radar - TODAY Manual Integrated Run
echo.
echo =============================================================
echo  GTA RADAR - ONE MANUAL FULL RUN TODAY
echo =============================================================
echo 1. Fast-forward installed CODE to verified GitHub main (only if safe).
echo 2. Run original Radar collection ONCE and shared capped AI.
echo 3. Run industrial, activation, facility, Toronto and council-item pilots.
echo 4. Include Brampton, Toronto and Mississauga council review outputs.
echo 5. Preserve dated results ZIP for upload and evidence review.
echo No daily scheduling, no automatic outreach, no extra AI budget.
echo.
where py >nul 2>nul
if not errorlevel 1 (
 set "PY_CMD=py -3"
) else (
 set "PY_CMD=python"
)
rem %%~dp0 ends with a backslash: a trailing slash before a closing quote
rem can escape that quote when Python parses the Windows command line.
rem After cd /d, %%CD%% is the resolved code directory without a trailing slash.
set "CODE_DIR=%CD%"
echo Checking local code and GitHub main without touching your database...
%PY_CMD% "%CODE_DIR%\desktop_update.py" --code-dir "%CODE_DIR%"
if errorlevel 1 (
 echo.
 echo STOP: Code was NOT verified and no collection was started.
 echo Local code changes and existing data have not been overwritten.
 echo Check Git, network access and any dirty or diverged tracked code.
 if /I not "%~1"=="--unattended" pause
 exit /b 3
)
echo.
echo Running integrated collection and bounded research pilots...
%PY_CMD% "%CODE_DIR%\gta_monday_full_run.py" %*
set "CODE=%ERRORLEVEL%"
echo.
echo Reports: existing new data\GTA_RADAR_RESULTS\MONDAY_FULL_RADAR
echo Dated evidence ZIP: existing new data\GTA_RADAR_EXPORTS
echo Read MONDAY_FULL_RADAR_STATUS.json for FAILED/PASSED stages.
echo Council items: COUNCIL_INTELLIGENCE_REVIEW (missing original docs remain HOLD).
echo If an original source is blocked, it remains blocked; no invented lead.
if not "%CODE%"=="0" echo One or more stages or ZIP packaging failed. Review the logs.
if /I not "%~1"=="--unattended" pause
exit /b %CODE%
