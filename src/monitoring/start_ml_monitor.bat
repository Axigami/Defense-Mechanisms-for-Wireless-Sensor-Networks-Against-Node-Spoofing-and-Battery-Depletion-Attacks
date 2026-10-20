@echo off
echo ============================================
echo ML Defense Monitor Server
echo Vampire Attack Detection Supervisor Console
echo ============================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8 or higher
    echo.
    pause
    exit /b 1
)

echo Python found: OK
echo.

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        echo.
        pause
        exit /b 1
    )
    echo Virtual environment created successfully
    echo.
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    echo Trying to run without virtual environment...
    echo.
)

REM Install requirements
echo Installing/Updating dependencies...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo WARNING: Some dependencies may not have been installed correctly
    echo Continuing anyway...
    echo.
)

REM Check for log file
set LOG_DIR=..\data\logs
set LOG_FILE=..\data\logs\run.log

echo.
echo ============================================
echo ML Defense Monitor:
echo   - Parses ML_ALERT logs from Contiki-NG nodes
echo   - Provides web dashboard for supervisor review
echo   - ACL auto-approve for clear-cut detections
echo   - Manual approve/reject for borderline cases
echo ============================================
echo.

if exist "%LOG_DIR%" (
    echo Log directory found: %LOG_DIR%
    echo Starting ML Monitor with log watching...
) else (
    echo Log directory not found: %LOG_DIR%
    echo Starting in API-only mode...
    echo Run Cooja simulation to generate logs
)

echo.
echo Dashboard will be available at:
echo   http://localhost:5003
echo.
echo Also running alongside:
echo   Main Monitor:     http://localhost:5000
echo   Attack Controller: http://localhost:5002
echo.
echo Press CTRL+C to stop the server
echo ============================================
echo.

REM Start the ML Monitor server
if exist "%LOG_DIR%" (
    python ml_monitor_server.py "%LOG_FILE%"
) else (
    echo Starting without log file (API-only mode)
    python ml_monitor_server.py
)

echo.
echo Server stopped.
pause
