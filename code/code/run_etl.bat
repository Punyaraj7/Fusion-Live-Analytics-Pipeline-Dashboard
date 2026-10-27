@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  py -3 main.py
) else (
  python main.py
)
if errorlevel 1 (
  echo.
  echo Python was not found. Install Python 3.10+ and try again.
  pause
)
