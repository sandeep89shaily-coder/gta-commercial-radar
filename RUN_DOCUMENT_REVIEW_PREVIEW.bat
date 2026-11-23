@echo off
setlocal
title GTA Radar - Document Intelligence Preview (NO AI)
cd /d "%~dp0"
echo.
echo GTA RADAR - SAFE DOCUMENT REVIEW
echo No DeepSeek calls. Does not run collectors or install tasks.
echo.
where py >nul 2>nul
if not errorlevel 1 (set "PY=py -3") else (set "PY=python")
%PY% --version >nul 2>nul
if errorlevel 1 (
 echo Python 3 is required. Existing GTA Radar already uses Python.
 pause
 exit /b 1
)
set "RESULTS="
if exist "%USERPROFILE%\Desktop\new data\GTA_RADAR_RESULTS\CANDIDATES_V4_ALL_REVIEW_ONLY.csv" set "RESULTS=%USERPROFILE%\Desktop\new data\GTA_RADAR_RESULTS"
if not defined RESULTS if exist "%USERPROFILE%\OneDrive\Desktop\new data\GTA_RADAR_RESULTS\CANDIDATES_V4_ALL_REVIEW_ONLY.csv" set "RESULTS=%USERPROFILE%\OneDrive\Desktop\new data\GTA_RADAR_RESULTS"
if not defined RESULTS if exist "%USERPROFILE%\Desktop\GTA_RADAR_RESULTS\CANDIDATES_V4_ALL_REVIEW_ONLY.csv" set "RESULTS=%USERPROFILE%\Desktop\GTA_RADAR_RESULTS"
if not defined RESULTS (
 echo.
 echo I couldn't automatically locate GTA_RADAR_RESULTS.
 echo Paste the full path to the EXISTING GTA_RADAR_RESULTS folder:
 set /p "RESULTS=Folder path: "
)
if not defined RESULTS goto :failed
set "RESULTS=%RESULTS:"=%"
if not exist "%RESULTS%\CANDIDATES_V4_ALL_REVIEW_ONLY.csv" (
 echo Candidate CSV not found in: "%RESULTS%"
 goto :failed
)
%PY% "%~dp0v8_document_bridge.py" --results "%RESULTS%"
if errorlevel 1 goto :failed
echo.
echo Preview completed. Opening the independent read-only review dashboard.
start "" "%RESULTS%\GTA_RADAR_DOCUMENT_OPERATIONS.html"
echo.
pause
exit /b 0
:failed
echo.
echo Preview NOT completed. No existing GTA Radar files were overwritten.
pause
exit /b 1
