@echo off
setlocal
title GTA Radar Meeting Transcription - Review Only
cd /d "%~dp0"
echo GTA RADAR - LOCAL MEETING TRANSCRIPTION
echo.
echo This tool requires an existing, lawfully obtained local audio/video file.
echo It does NOT download meeting videos, use DeepSeek, or publish leads.
echo.
if "%~1"=="" (
  set /p "MEDIA=Paste full local audio/video path: "
) else (
  set "MEDIA=%~1"
)
set /p "MEETING_URL=Paste original public HTTPS meeting page/video URL: "
if not defined MEDIA goto done
if not defined MEETING_URL goto done
where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (set "PY=py -3") else (set "PY=python")
echo.
echo Local speech recognition requires faster-whisper:
echo    %PY% -m pip install faster-whisper
echo Note: First use may download a speech model. No paid API calls.
echo.
choice /C YN /N /M "Run CPU transcription now? [Y/N]: "
if errorlevel 2 goto done
%PY% municipal_meeting_transcription.py --media "%MEDIA%" --meeting-url "%MEETING_URL%" --out "%~dp0MEETING_REVIEW" --device cpu --compute-type int8
if errorlevel 1 (
 echo Transcription failed; check faster-whisper installation and local recording.
 goto done
)
echo.
echo Review: "%~dp0MEETING_REVIEW\MEETING_TRANSCRIPT.csv"
echo This is NOT a verified lead list.
:done
pause
