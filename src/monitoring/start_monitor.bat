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

REM Find log file - check multiple locations
set LOG_FILE=..\data\logs\run.log
set LOG_FILE_ABS=%~dp0..\data\logs\run.log

echo.
echo ============================================
echo Searching for log files...
echo.

REM Check if log file exists
if exist "%LOG_FILE%" (
    for %%F in ("%LOG_FILE%") do (
        echo Log file found: %%~fF
        echo Size: %%~zF bytes
    )
    set FOUND_LOG=1
) else (
    echo Log file not found: %LOG_FILE%
    set FOUND_LOG=0
)

echo.
if "%FOUND_LOG%"=="1" (
    echo Starting server with log monitoring...
    echo Server will read ALL run*.log files in the logs folder
) else (
    echo WARNING: No log file found!
    echo Starting server in API-only mode...
    echo.
    echo To use monitoring:
    echo   1. Run Cooja simulation
    echo   2. Ensure log is saved to: %LOG_FILE_ABS%
    echo   3. Restart this server
)

echo.
echo Dashboard will be available at:
echo   http://localhost:5000
echo.
echo Press CTRL+C to stop the server
echo ============================================
echo.

REM Start the server
if "%FOUND_LOG%"=="1" (
    echo Starting with log file: %LOG_FILE%
    python monitor_server.py "%LOG_FILE%"
) else (
    echo Starting without log file (API-only mode)
    python monitor_server.py
)

echo.
echo Server stopped.
pause
