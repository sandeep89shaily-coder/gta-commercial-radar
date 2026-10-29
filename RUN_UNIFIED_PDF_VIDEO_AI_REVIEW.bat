@echo off
setlocal
title GTA Radar - PDF and Meeting DeepSeek Intelligence
cd /d "%~dp0"
set "RESULTS=%USERPROFILE%\Desktop\new data\GTA_RADAR_RESULTS"
if not exist "%RESULTS%\" set "RESULTS=%USERPROFILE%\OneDrive\Desktop\new data\GTA_RADAR_RESULTS"
if not exist "%RESULTS%\" (echo Existing shared GTA_RADAR_RESULTS folder not found. & pause & exit /b 1)
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (set "PY=py -3") else (set "PY=python")
echo.
echo Choose input type:
echo 1. Existing PDF (text-readable)
echo 2. Existing meeting transcript CSV
echo 3. Existing local meeting audio/video (Whisper installed)
choice /C 123 /N /M "Select 1, 2, or 3: "
set "TYPE=%ERRORLEVEL%"
if "%TYPE%"=="1" (set /p "SOURCE_PATH=Full PDF file path: " & set "FLAG=--pdf")
if "%TYPE%"=="2" (set /p "SOURCE_PATH=Full transcript CSV path: " & set "FLAG=--transcript")
if "%TYPE%"=="3" (set /p "SOURCE_PATH=Full local audio/video file path: " & set "FLAG=--media")
set /p "URL=Official HTTPS source URL: "
if not defined SOURCE_PATH goto done
if not defined URL goto done
echo.
echo Stage 1: no-cost source coverage preflight.
if "%TYPE%"=="3" goto media
%PY% municipal_unified_intelligence.py %FLAG% "%SOURCE_PATH%" --source-url "%URL%" --results "%RESULTS%" --out "%~dp0UNIFIED_INTELLIGENCE_REVIEW"
if errorlevel 1 goto fail
goto approval
:media
echo Local faster-whisper required; first use downloads model. No audio upload.
%PY% -c "import faster_whisper" 2>nul
if errorlevel 1 (echo Run: %PY% -m pip install faster-whisper & goto fail)
%PY% municipal_unified_intelligence.py --media "%SOURCE_PATH%" --source-url "%URL%" --results "%RESULTS%" --out "%~dp0UNIFIED_INTELLIGENCE_REVIEW"
if errorlevel 1 goto fail
set "SOURCE_PATH=%~dp0UNIFIED_INTELLIGENCE_REVIEW\MEETING_TRANSCRIPT.csv"
set "FLAG=--transcript"
:approval
echo.
echo DeepSeek analysis is OPTIONAL. Existing shared ledger and USD 0.25 daily ceiling apply.
echo Each chunk uses a separate reservation; default maximum is 3.
choice /C YN /N /M "Authorize up to 3 DeepSeek requests now? [Y/N]: "
if errorlevel 2 goto done
%PY% municipal_unified_intelligence.py %FLAG% "%SOURCE_PATH%" --source-url "%URL%" --results "%RESULTS%" --out "%~dp0UNIFIED_INTELLIGENCE_REVIEW" --paid --max-chunks 3
if errorlevel 1 goto fail
echo See UNIFIED_COVERAGE.json and UNIFIED_EVIDENCE.json in UNIFIED_INTELLIGENCE_REVIEW.
goto done
:fail
echo The operation stopped. No automatic retry.
:done
pause
