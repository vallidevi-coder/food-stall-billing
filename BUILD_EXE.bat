@echo off
cd /d "%~dp0"
python -m pip install -r requirements.txt pyinstaller
pyinstaller --onefile --add-data "templates;templates" --add-data "static;static" app.py
echo.
echo EXE created inside the dist folder.
pause
