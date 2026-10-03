@echo off
REM openclaw-upload.bat
REM Windows wrapper for openclaw-upload.py
REM Place next to openclaw-upload.py. Run from any directory.

SET SCRIPT_DIR=%~dp0
SET SCRIPT=%SCRIPT_DIR%openclaw-upload.py

REM Check Python
python --version >nul 2>&1
IF ERRORLEVEL 1 (
    echo ERROR: Python not found. Install Python 3.9+ from https://python.org
    exit /b 1
)

REM Check requests
python -c "import requests" >nul 2>&1
IF ERRORLEVEL 1 (
    echo Installing required dependency: requests
    pip install requests --quiet
)

python "%SCRIPT%" %*
