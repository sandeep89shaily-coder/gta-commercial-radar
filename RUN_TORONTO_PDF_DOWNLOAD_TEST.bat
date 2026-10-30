@echo off
setlocal
title GTA Radar - Toronto real PDF download validation
cd /d "%~dp0"
echo.
echo GTA Radar: checking one real official Toronto staff-report PDF.
echo The test does NOT update production V8 or call any paid AI.
echo.
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  set "PY=py -3"
) else (
  set "PY=python"
)
%PY% -c "import requests,pypdf" >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python needs requests and pypdf packages.
  echo Install with: py -3 -m pip install -r requirements.txt
  echo No network request was made to Toronto.
  pause
  exit /b 1
)
%PY% "%~dp0toronto_pdf_download.py" --url "https://www.toronto.ca/legdocs/mmis/2026/cc/bgrd/backgroundfile-287146.pdf" --out "%~dp0TORONTO_PDF_VALIDATION" --fetch
echo.
echo Inspect PDF and audit under:
echo "%~dp0TORONTO_PDF_VALIDATION"
echo.
pause
