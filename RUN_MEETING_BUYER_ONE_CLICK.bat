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
set /p "RECORDING=Optional official meeting video URL for provenance: "
set /p "CAPTION=Optional full path to authorized local VTT/SRT caption file: "
set /p "ADDRESS=Optional project street address for official-source research: "
if defined CAPTION (
 if not defined RECORDING (echo Caption needs original recording URL. & goto buyer)
 %PY% municipal_captions_to_transcript.py --captions "%CAPTION%" --url "%RECORDING%" --out "%OUT%\MEETING_TRANSCRIPT.csv"
 if errorlevel 1 goto fail
 echo Transcript ready for DeepSeek in RUN_UNIFIED_PDF_VIDEO_AI_REVIEW.bat.
)
goto buyer
:buyer
if defined ADDRESS %PY% RUN_MEETING_BUYER_PIPELINE.py --city "%CITY%" --out "%OUT%" --address "%ADDRESS%"
goto done
:fail
echo Review failed, check official source access and output folder.
:done
pause
