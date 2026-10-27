@echo off
setlocal
cd /d "%~dp0"
title GTA Radar - Official document preview
where py >nul 2>nul
if not errorlevel 1 (set "PY=py -3") else (set "PY=python")
set "RESULTS="
if exist "%USERPROFILE%\Desktop\new data\GTA_RADAR_RESULTS\CANDIDATES_V4_ALL_REVIEW_ONLY.csv" set "RESULTS=%USERPROFILE%\Desktop\new data\GTA_RADAR_RESULTS"
if not defined RESULTS if exist "%USERPROFILE%\OneDrive\Desktop\new data\GTA_RADAR_RESULTS\CANDIDATES_V4_ALL_REVIEW_ONLY.csv" set "RESULTS=%USERPROFILE%\OneDrive\Desktop\new data\GTA_RADAR_RESULTS"
if not defined RESULTS (
 echo Paste your EXISTING GTA_RADAR_RESULTS folder path:
 set /p "RESULTS=Folder: "
)
set "RESULTS=%RESULTS:"=%"
if not exist "%RESULTS%\CANDIDATES_V4_ALL_REVIEW_ONLY.csv" goto :failed
echo.
echo This pilot checks UP TO SIX already-linked official source pages.
echo It cannot retrieve blocked sites or PDFs, and uses no AI.
echo.
%PY% "%~dp0v8_official_document_capture.py" --results "%RESULTS%" --fetch --max-pages 6
if errorlevel 1 goto :failed
%PY% "%~dp0v8_document_bridge.py" --results "%RESULTS%"
if errorlevel 1 goto :failed
start "" "%RESULTS%\GTA_RADAR_DOCUMENT_OPERATIONS.html"
echo.
echo Preview complete. Your normal V8 program and schedule were not changed.
pause
exit /b 0
:failed
echo Preview failed; original V8 source files were not modified.
pause
exit /b 1
