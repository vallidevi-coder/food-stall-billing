@echo off
title NextGen Food Stall
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python is not installed. Please install Python 3.11+ first.
  pause
  exit /b 1
)
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Could not install required packages.
  pause
  exit /b 1
)
python app.py
pause
