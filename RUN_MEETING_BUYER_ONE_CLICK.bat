@echo off
setlocal
title GTA Radar - Meeting and Buyer Intelligence
cd /d "%~dp0"
where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (set "PY=py -3") else (set "PY=python")
echo Official municipal meeting discovery and buyer evidence review.
choice /C TB /N /M "Choose Toronto [T] or Brampton [B]: "
if errorlevel 2 (set "CITY=Brampton") else (set "CITY=Toronto")
set "OUT=%~dp0MUNICIPAL_MEETING_BUYER_REVIEW\%CITY%"
echo Step 1: discover recording links and create preliminary evidence graph.
%PY% RUN_MEETING_BUYER_PIPELINE.py --city "%CITY%" --out "%OUT%" --discover-archive
if errorlevel 1 goto fail
echo.
echo See "%OUT%\%CITY%_MEETINGS.json" for official-source recording links.
set /p "RECORDING=To capture captions, paste one exact discovered recording URL (or press Enter to skip): "
set /p "ADDRESS=Optional project street address for official procurement source check: "
if not defined RECORDING goto buyer
echo.
echo Caption retrieval uses yt-dlp and requires permission to access/reuse.
choice /C YN /N /M "Authorize capture of PUBLIC captions for this recording? [Y/N]: "
if errorlevel 2 goto buyer
%PY% -c "import yt_dlp" 2>nul
if errorlevel 1 (
 choice /C YN /N /M "Install yt-dlp now? [Y/N]: "
 if errorlevel 2 goto buyer
 %PY% -m pip install yt-dlp
 if errorlevel 1 goto fail
)
if defined ADDRESS (
 %PY% RUN_MEETING_BUYER_PIPELINE.py --city "%CITY%" --out "%OUT%" --recording-url "%RECORDING%" --authorize-caption-capture --address "%ADDRESS%"
) else (
 %PY% RUN_MEETING_BUYER_PIPELINE.py --city "%CITY%" --out "%OUT%" --recording-url "%RECORDING%" --authorize-caption-capture
)
if errorlevel 1 goto fail
if exist "%OUT%\MEETING_TRANSCRIPT.csv" echo Captions are ready for DeepSeek via RUN_UNIFIED_PDF_VIDEO_AI_REVIEW.bat
goto done
:buyer
if defined ADDRESS %PY% RUN_MEETING_BUYER_PIPELINE.py --city "%CITY%" --out "%OUT%" --address "%ADDRESS%"
goto done
:fail
echo Review failed, check official source access and output folder.
:done
pause
