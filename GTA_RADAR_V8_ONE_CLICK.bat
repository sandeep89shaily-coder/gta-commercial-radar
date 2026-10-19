@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title GTA Radar V8 - Native DeepSeek Search
where py >nul 2>nul
if not errorlevel 1 (set "PY=py -3") else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python 3 is not installed. Your saved databases have not been changed.
    pause
    exit /b 1
  )
  set "PY=python"
)
echo GTA Radar V8 - DeepSeek Search, Fetch and Flash

echo Downloading the verified program from your GitHub repository...
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $dest=Join-Path $env:LOCALAPPDATA 'GTACommercialRadar\V8'; $zip=Join-Path $env:TEMP ('radar_v8_'+[guid]::NewGuid().ToString('N')+'.zip'); $tempdir=Join-Path $env:TEMP ('radar_v8_unpack_'+[guid]::NewGuid().ToString('N')); try { Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/sandeep89shaily-coder/gta-commercial-radar/archive/refs/heads/main.zip' -OutFile $zip; Expand-Archive -LiteralPath $zip -DestinationPath $tempdir -Force; $src=Get-ChildItem -LiteralPath $tempdir -Directory | Select-Object -First 1; if (-not $src) { throw 'Download empty' }; foreach ($file in @('v8_deepseek_native.py','v6_daily_pipeline.py','v5_investigator.py','commercial_selector_v4.py','main.py')) { if (-not (Test-Path -LiteralPath (Join-Path $src.FullName $file))) { throw ('Missing required file: '+$file) } }; New-Item -ItemType Directory -Force -Path $dest | Out-Null; Copy-Item -Path (Join-Path $src.FullName '*') -Destination $dest -Recurse -Force; Write-Host 'V8 installed. Your old data was not moved.' } catch { Write-Host ('Could not install: '+$_.Exception.Message); exit 1 } finally { Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue; Remove-Item -LiteralPath $tempdir -Recurse -Force -ErrorAction SilentlyContinue }"
if errorlevel 1 (
 echo Installation stopped without replacing your original database.
 pause
 exit /b 1
)
echo Running collection, native DeepSeek discovery, and Flash analysis...
echo The same US$0.50/day software allowance includes earlier Radar DeepSeek usage.
%PY% -u "%LOCALAPPDATA%\GTACommercialRadar\V8\v6_daily_pipeline.py"
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" echo Please send a screenshot of this window if an error occurred.
echo.
echo Finished. Press any key to close.
pause >nul
exit /b %RESULT%