@echo off
setlocal
cd /d "%~dp0"
title GTA Commercial Radar - Phase 1 Combined Test

echo.
echo ================================================
echo  BRAMPTON + TORONTO + MISSISSAUGA INTEGRATION TEST
echo ================================================
echo This tests the latest GitHub code across all three cities.
echo Existing SQLite databases and historical checkpoints stay intact.
echo Collector results and errors are collected in one diagnostic ZIP.
echo This may take some time; keep the window open until it finishes.
echo.

where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
%PY% --version >nul 2>nul
if errorlevel 1 (
 echo Python could not be found.
 pause
 exit /b 1
)
%PY% -c "import requests, bs4, pypdf, pandas, openpyxl" >nul 2>nul
if errorlevel 1 (
 echo Installing required dependencies...
 %PY% -m pip install -r requirements.txt
 if errorlevel 1 (
  echo Dependency installation failed. Existing data was not modified.
  pause
  exit /b 1
 )
)
%PY% phase1_test.py
set "RESULT=%errorlevel%"

echo.
echo ================================================
echo  TEST FINISHED
echo  Please upload: data\PHASE1_TEST_RESULTS.zip
echo  Raw logs and SQLite databases stay on your PC.
echo ================================================
echo.
pause
exit /b %RESULT%
