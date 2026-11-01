@echo off
setlocal
cd /d "%~dp0"
title GTA Radar - Gemini key check (no cost)
echo.
echo GEMINI API KEY DIAGNOSTIC -- NO PAID RESEARCH
echo This checks Gemini model metadata only.
echo It does NOT generate text, perform Google searches, or use your Radar budget.
echo If asked for a key, input is hidden and is not written to disk.
echo.
where py >nul 2>nul
if not errorlevel 1 (
    py -3 "%~dp0gta_google_grounding_pilot.py" --diagnose-key --prompt-key
    goto finished_python
)
where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python 3 is not available on PATH.
    set "RESULT=1"
    goto finished
)
python "%~dp0gta_google_grounding_pilot.py" --diagnose-key --prompt-key
:finished_python
set "RESULT=%errorlevel%"
:finished
echo.
echo MODEL_LOOKUP_OK means your key can read model metadata.
echo It does NOT confirm paid billing or Search grounding is enabled.
echo MODEL_LOOKUP_FAILED displays a redacted Google HTTP error to diagnose.
echo Do not share your API key or screenshots containing it.
echo.
if /I not "%~1"=="--unattended" pause
exit /b %RESULT%
