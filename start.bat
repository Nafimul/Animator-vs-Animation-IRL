@echo off
echo ========================================
echo  Animator vs Animation IRL - Quick Start
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from https://python.org
    pause
    exit /b 1
)

REM Check if venv exists, create if not
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

REM Activate venv
echo Activating virtual environment...
call .venv\Scripts\activate.bat

REM Check if requirements are installed
pip show PyQt6 >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
)

REM Check if .env exists
if not exist ".env" (
    echo.
    echo WARNING: .env file not found!
    echo Please copy .env.example to .env and add your API keys
    echo.
    pause
    exit /b 1
)

REM Run the application
echo.
echo Starting application...
echo.
python App.py

pause
