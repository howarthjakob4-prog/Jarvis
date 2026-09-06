@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Jarvis is not set up yet. Running setup first...
  call SETUP_WINDOWS.bat
  if errorlevel 1 exit /b 1
)
".venv\Scripts\python.exe" main.py
if errorlevel 1 (
  echo.
  echo Jarvis exited with an error. Check logs\jarvis.log for details.
  pause
)
