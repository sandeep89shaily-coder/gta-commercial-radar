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
echo 4. Scanned PDF (DeepSeek vision OCR, paid)
choice /C 1234 /N /M "Select 1, 2, 3 or 4: "
set "TYPE=%ERRORLEVEL%"
if "%TYPE%"=="1" (set /p "SOURCE_PATH=Full PDF file path: " & set "FLAG=--pdf")
if "%TYPE%"=="2" (set /p "SOURCE_PATH=Full transcript CSV path: " & set "FLAG=--transcript")
if "%TYPE%"=="3" (set /p "SOURCE_PATH=Full local audio/video file path: " & set "FLAG=--media")
if "%TYPE%"=="4" (set /p "SOURCE_PATH=Full scanned PDF file path: " & set "FLAG=--pdf")
set /p "URL=Official HTTPS source URL: "
if not defined SOURCE_PATH goto done
if not defined URL goto done
for %%G in ("%SOURCE_PATH%") do set "NAME=%%~nG"
set "REVIEW_OUT=%~dp0UNIFIED_REVIEWS\%NAME%"
echo.
echo Stage 1: no-cost source coverage preflight.
if "%TYPE%"=="3" goto media
if "%TYPE%"=="4" goto scanned
%PY% municipal_unified_intelligence.py %FLAG% "%SOURCE_PATH%" --source-url "%URL%" --results "%RESULTS%" --out "%REVIEW_OUT%"
if errorlevel 1 goto fail
goto approval
:media
echo Local faster-whisper required; first use downloads model. No audio upload.
%PY% -c "import faster_whisper" 2>nul
if errorlevel 1 (echo Run: %PY% -m pip install faster-whisper & goto fail)
%PY% municipal_unified_intelligence.py --media "%SOURCE_PATH%" --source-url "%URL%" --results "%RESULTS%" --out "%REVIEW_OUT%"
if errorlevel 1 goto fail
set "SOURCE_PATH=%REVIEW_OUT%\MEETING_TRANSCRIPT.csv"
set "FLAG=--transcript"
goto approval
:scanned
echo DeepSeek vision OCR is paid; no automatic PDF upload without your approval.
echo First installing PyMuPDF if needed: %PY% -m pip install pymupdf
%PY% -c "import fitz" 2>nul
if errorlevel 1 (echo Run: %PY% -m pip install pymupdf & goto fail)
%PY% municipal_pdf_vision_ocr.py --pdf "%SOURCE_PATH%" --source-url "%URL%" --results "%RESULTS%" --out "%REVIEW_OUT%"
if errorlevel 1 goto fail
echo This route reserves up to USD 0.04 per page and never bypasses the USD 0.25 cap.
choice /C YN /N /M "Authorize vision OCR of up to 2 scanned pages? [Y/N]: "
if errorlevel 2 goto done
%PY% municipal_pdf_vision_ocr.py --pdf "%SOURCE_PATH%" --source-url "%URL%" --results "%RESULTS%" --out "%REVIEW_OUT%" --paid --max-pages 2
if errorlevel 1 goto fail
set "SOURCE_PATH=%REVIEW_OUT%\PDF_OCR_PAGES.csv"
set "FLAG=--ocr-csv"
:approval
echo.
echo DeepSeek analysis is OPTIONAL. Existing shared ledger and USD 0.25 daily ceiling apply.
echo Each chunk uses a separate reservation; default maximum is 3.
choice /C YN /N /M "Authorize up to 3 DeepSeek requests now? [Y/N]: "
if errorlevel 2 goto done
%PY% municipal_unified_intelligence.py %FLAG% "%SOURCE_PATH%" --source-url "%URL%" --results "%RESULTS%" --out "%REVIEW_OUT%" --paid --max-chunks 3
if errorlevel 1 goto fail
echo Review outputs saved in "%REVIEW_OUT%"
choice /C YN /N /M "Compare with another completed PDF or meeting review? [Y/N]: "
if errorlevel 2 goto done
set /p "OTHER=Full path to OTHER UNIFIED_EVIDENCE.json: "
if not exist "%OTHER%" (echo Other review not found. & goto done)
%PY% municipal_cross_source_synthesis.py --reviews "%REVIEW_OUT%\UNIFIED_EVIDENCE.json" "%OTHER%" --results "%RESULTS%" --out "%REVIEW_OUT%\CROSS_SOURCE_SYNTHESIS.json"
if errorlevel 1 goto fail
choice /C YN /N /M "Authorize one budgeted DeepSeek cross-source synthesis? [Y/N]: "
if errorlevel 2 goto done
%PY% municipal_cross_source_synthesis.py --reviews "%REVIEW_OUT%\UNIFIED_EVIDENCE.json" "%OTHER%" --results "%RESULTS%" --out "%REVIEW_OUT%\CROSS_SOURCE_SYNTHESIS.json" --paid
goto done
:fail
echo The operation stopped. No automatic retry.
:done
pause
