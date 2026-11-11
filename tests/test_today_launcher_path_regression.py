"""Regression for the Windows launcher code-dir quoted trailing-backslash bug.

The original --code-dir "%~dp0" passed a directory ending in a backslash
before the quote; Windows subprocess argument parsing can swallow the quote.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_today_launcher_passes_canonical_directory_not_dp0():
    code = (ROOT / "RUN_GTA_RADAR_TODAY.bat").read_text(encoding="utf-8")
    assert 'cd /d "%~dp0"' in code
    assert 'set "CODE_DIR=%CD%"' in code
    assert '--code-dir "%CODE_DIR%"' in code
    assert '--code-dir "%~dp0"' not in code
    assert '"%CODE_DIR%\\desktop_update.py"' in code
    assert '"%CODE_DIR%\\gta_monday_full_run.py"' in code
    assert 'if errorlevel 1 (' in code
    assert 'exit /b 3' in code
