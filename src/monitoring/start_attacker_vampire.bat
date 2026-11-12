@echo off
REM ============================================
REM VAMPIRE ATTACK CONTROLLER WEB SERVER
REM Start Flask server để control attacks qua browser
REM ============================================

echo.
echo ============================================
echo VAMPIRE ATTACK CONTROLLER - WEB SERVER
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

REM Check if Flask is installed
python -c "import flask" 2>nul
if errorlevel 1 (
    echo Flask not found. Installing...
    pip install flask flask-cors
)

echo Starting Vampire Attack Controller...
echo.
echo Dashboard will be available at:
echo   http://localhost:5002
echo.
echo Press CTRL+C to stop the server
echo ============================================
echo.

python attacker_vampire_server.py

pause
