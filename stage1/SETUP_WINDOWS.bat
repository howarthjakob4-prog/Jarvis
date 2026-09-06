@echo off
setlocal
cd /d "%~dp0"

echo [Jarvis] Checking Python...
py -3.11 --version >nul 2>&1
if errorlevel 1 (
  echo Python 3.11 was not found.
  echo Install Python 3.11 from python.org, then run this file again.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [Jarvis] Creating local Python environment...
  py -3.11 -m venv .venv
  if errorlevel 1 goto :fail
)

echo [Jarvis] Updating pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :fail

echo [Jarvis] Installing Jarvis dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :fail

echo.
echo Setup complete. Double-click RUN_JARVIS.bat to start Jarvis.
pause
exit /b 0

:fail
echo.
echo Setup failed. Read the error above. Nothing was reported as successful.
pause
exit /b 1
