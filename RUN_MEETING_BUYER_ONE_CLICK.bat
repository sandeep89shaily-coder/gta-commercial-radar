@echo off
setlocal
title GTA Radar - Official Meeting and Buyer Intelligence
cd /d "%~dp0"
where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (set "PY=py -3") else (set "PY=python")
set "OUT=%~dp0MUNICIPAL_MEETING_BUYER_REVIEW"
set "RESULTS=%USERPROFILE%\Desktop\new data\GTA_RADAR_RESULTS"
if not exist "%RESULTS%\" set "RESULTS=%USERPROFILE%\OneDrive\Desktop\new data\GTA_RADAR_RESULTS"
echo GTA RADAR - Official municipal meeting and purchasing evidence
choice /C TB /N /M "Toronto [T] or Brampton [B]? "
if errorlevel 2 (set "CITY=Brampton") else (set "CITY=Toronto")
set "OUT=%OUT%\%CITY%"
echo Checking official municipal index and permitted metadata.
%PY% RUN_MEETING_BUYER_PIPELINE.py --city "%CITY%" --out "%OUT%" --discover-archive --include-procurement
if errorlevel 1 goto fail
echo.
echo Recording leads: "%OUT%\%CITY%_MEETINGS.json"
if exist "%OUT%\TORONTO_OFFICIAL_PROCUREMENT.json" %PY% -c "import json,sys; d=json.load(open(sys.argv[1],encoding='utf-8')); print('Toronto procurement:',len(d.get('records',[])),'records;',d.get('status')); [print('SOURCE FAILURE:',x.get('error_type'),x.get('error_detail','')) for x in d.get('page_audit',[]) if x.get('status')=='FAILED']" "%OUT%\TORONTO_OFFICIAL_PROCUREMENT.json"
if exist "%OUT%\MUNICIPAL_INTELLIGENCE_REVIEW.html" start "" "%OUT%\MUNICIPAL_INTELLIGENCE_REVIEW.html"
echo.
echo Optional extended analysis: You can skip all inputs to finish now.
choice /C YN /N /M "Investigate a specific video, caption or project address? [Y/N]: "
if errorlevel 2 goto done
echo YouTube metadata access does NOT grant permission to download recordings.
set /p "RECORDING=Original official meeting video URL (blank if none): "
set /p "CAPTION=Authorized local VTT/SRT caption path (blank if none): "
set /p "ADDRESS=Project street address to investigate (blank if none): "
if not defined CAPTION goto buyer
if not defined RECORDING (
 echo A source URL is required to preserve caption provenance.
 goto buyer
)
%PY% municipal_captions_to_transcript.py --captions "%CAPTION%" --url "%RECORDING%" --out "%OUT%\MEETING_TRANSCRIPT.csv"
if errorlevel 1 goto fail
echo Timestamped captions imported. No speech facts verified yet.
if not exist "%RESULTS%\" goto buyer
choice /C YN /N /M "Authorize up to 3 DeepSeek transcript analysis requests (USD 0.25 daily cap)? [Y/N]: "
if errorlevel 2 goto buyer
%PY% municipal_unified_intelligence.py --transcript "%OUT%\MEETING_TRANSCRIPT.csv" --source-url "%RECORDING%" --results "%RESULTS%" --out "%OUT%\DEEPSEEK_TRANSCRIPT_REVIEW" --paid --max-chunks 3
if errorlevel 1 goto fail
:buyer
if not defined ADDRESS goto done
%PY% RUN_MEETING_BUYER_PIPELINE.py --city "%CITY%" --out "%OUT%" --discover-archive --include-procurement --address "%ADDRESS%"
if errorlevel 1 goto fail
echo Buyer source evidence: "%OUT%\BUYER_OFFICIAL_SOURCE_AUDIT.json"
if not exist "%RESULTS%\" goto done
choice /C YN /N /M "Authorize DeepSeek to investigate cited official buyer-role evidence? [Y/N]: "
if errorlevel 2 goto done
%PY% RUN_MEETING_BUYER_PIPELINE.py --city "%CITY%" --out "%OUT%" --discover-archive --include-procurement --address "%ADDRESS%" --deepseek-buyer --results "%RESULTS%"
if errorlevel 1 goto fail
echo Review graph: "%OUT%\PROJECT_EVIDENCE_GRAPH.json"
goto done
:fail
echo An operation failed. No automatic paid retry and no production changes.
:done
pause
