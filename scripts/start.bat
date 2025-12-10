@echo off
REM Start script for voice AI bot (Windows)

echo ==========================================
echo Starting Voice AI Bot
echo ==========================================

REM Check if .env exists
if not exist .env (
    echo Error: .env file not found!
    echo Please copy .env.example to .env and configure it.
    exit /b 1
)

REM Check if virtual environment exists
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install/upgrade dependencies
echo Installing dependencies...
pip install -r requirements.txt

REM Create necessary directories
echo Creating directories...
if not exist logs mkdir logs
if not exist debug_audio mkdir debug_audio
if not exist knowledge mkdir knowledge

REM Run the application
echo Starting application...
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
