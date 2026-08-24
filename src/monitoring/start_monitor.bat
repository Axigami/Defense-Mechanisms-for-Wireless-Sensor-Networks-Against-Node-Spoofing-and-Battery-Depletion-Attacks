@echo off
echo ============================================
echo WSN Real-time Monitoring Server
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
set LOG_FILE=..\data\logs\run.log

echo.
echo ============================================
if exist "%LOG_FILE%" (
    echo Log file found: %LOG_FILE%
    echo Starting server with log monitoring...
) else (
    echo Log file not found: %LOG_FILE%
    echo Starting server in API-only mode...
    echo You can run Cooja simulation to generate logs later
)
echo.
echo Dashboard will be available at:
echo   http://localhost:5000
echo.
echo Press CTRL+C to stop the server
echo ============================================
echo.

REM Start the server (with or without log file)
if exist "%LOG_FILE%" (
    python monitor_server.py "%LOG_FILE%"
) else (
    python monitor_server.py
)

echo.
echo Server stopped.
pause
