@echo off
REM Startup script for Trading Backend
REM This script tests all broker connections and starts the backend server

echo.
echo ===============================================================================
echo   Trading Backend - Startup Script
echo ===============================================================================
echo.

REM Change to script directory
cd /d "%~dp0"

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python 3.8 or higher
    pause
    exit /b 1
)

REM Check if virtual environment should be used
if exist "venv\Scripts\activate.bat" (
    echo [INFO] Activating virtual environment...
    call venv\Scripts\activate.bat
)

REM Check if dependencies are installed
echo.
echo [INFO] Checking dependencies...
pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo [WARN] Dependencies not installed. Installing now...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies
        pause
        exit /b 1
    )
)

REM Test all broker connections
echo.
echo [INFO] Testing broker connections...
echo.
python test_all_brokers.py
if errorlevel 1 (
    echo.
    echo ===============================================================================
    echo [WARN] Some broker connections failed!
    echo ===============================================================================
    echo.
    choice /C YN /M "Do you want to start the backend server anyway"
    if errorlevel 2 goto :end
)

REM Start the backend server
echo.
echo ===============================================================================
echo [INFO] Starting backend server on http://localhost:8000
echo ===============================================================================
echo.
echo Press Ctrl+C to stop the server
echo.

python backend_server.py

:end
echo.
echo [INFO] Backend server stopped
pause
