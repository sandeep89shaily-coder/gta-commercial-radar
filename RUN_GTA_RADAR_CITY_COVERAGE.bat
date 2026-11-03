@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
    set "GTA_WORKSPACE=%USERPROFILE%\Desktop\new data"
) else (
    if /I "%~1"=="--workspace" (
        set "GTA_WORKSPACE=%~2"
    ) else (
        set "GTA_WORKSPACE=%~1"
    )
)
if not exist "%GTA_WORKSPACE%" (
    echo Workspace not found: "%GTA_WORKSPACE%"
    exit /b 2
)
python gta_city_coverage_check.py --workspace "%GTA_WORKSPACE%"
if errorlevel 1 (
    echo Coverage test encountered an error. Existing results are not deleted.
    exit /b 1
)
echo.
echo Coverage audit finished. No paid DeepSeek research was run.
exit /b 0
