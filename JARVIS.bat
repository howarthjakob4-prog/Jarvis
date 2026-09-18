@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python not found. Install Python 3.12 or newer from https://www.python.org/downloads/
  echo Make sure to tick "Add python.exe to PATH" during install.
  pause
  exit /b 1
)

echo Installing Jarvis requirements...
python -m pip install --upgrade pip >nul 2>nul
pip install -r requirements.txt
if errorlevel 1 (
  echo Install failed. Check your internet connection and try again.
  pause
  exit /b 1
)

if not exist "config\local.yaml" (
  echo First run: setup wizard.
  echo (Everything is optional - press Enter to skip through.)
  python -m jarvis.setup_wizard
)

echo Starting Jarvis...
python -m jarvis
pause
