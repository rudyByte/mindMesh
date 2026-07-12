@echo off
title MindMesh Launcher
cd /d "%~dp0"

echo ============================================
echo    MindMesh - Starting All Services
echo ============================================
echo.

:: --- Kill any existing Next.js dev server on port 3000 ---
echo [cleanup] Checking for existing dev servers...
powershell -Command "Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue | ForEach-Object { Write-Host ('[cleanup] Stopping old process on port 3000 (PID ' + $_.OwningProcess + ')...'); Stop-Process -Id $_.OwningProcess -Force }" 2>nul
timeout /t 1 /nobreak >nul 2>nul

:: --- Ensure web/.env.local exists ---
if not exist web\.env.local (
  echo [setup] Creating web/.env.local with API URL...
  echo NEXT_PUBLIC_API_URL=http://localhost:8000 > web\.env.local
) else (
  echo [setup] web/.env.local found
)

echo.
echo [1/2] Starting Python FastAPI backend (port 8000)...
start "MindMesh Backend" cmd /k "python -m uvicorn server.main:app --reload --host 127.0.0.1 --port 8000"

:: Small pause to let backend start
timeout /t 2 /nobreak >nul

echo [2/2] Starting Next.js frontend (port 3000)...
start "MindMesh Frontend" cmd /k "cd /d web && npm run dev"

echo.
echo ============================================
echo   Both servers are starting up!
echo   Frontend: http://localhost:3000
echo   Backend:  http://localhost:8000
echo ============================================
echo.
echo Close the server windows to stop them.
echo Or press Ctrl+C in this window if you started this from a terminal.
echo.
pause
