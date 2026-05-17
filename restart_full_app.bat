@echo off
echo ===============================================================================
echo   Restarting Full Stack Application (Backend + Frontend)
echo ===============================================================================
echo.

echo [INFO] Stopping existing Python (Backend) processes...
taskkill /F /IM python.exe /T 2>nul
if errorlevel 1 (
    echo [INFO] No running Python processes found.
) else (
    echo [SUCCESS] Python processes stopped.
)

echo.
echo [INFO] Stopping existing Node.js (Frontend) processes...
taskkill /F /IM node.exe /T 2>nul
if errorlevel 1 (
    echo [INFO] No running Node.js processes found.
) else (
    echo [SUCCESS] Node.js processes stopped.
)

echo.
echo [INFO] Starting Backend Server...
start "Trading Backend" cmd /k "python backend_server.py"

echo.
echo [INFO] Starting Frontend Dev Server...
cd frontend
start "Trading Frontend" cmd /k "npm run dev"
cd ..

echo.
echo ===============================================================================
echo   Application Restarted!
echo   Backend: http://localhost:8000
echo   Frontend: http://localhost:5173
echo ===============================================================================
echo.
pause
