@echo off
REM AlphaMarkA Production Startup Script
REM Starts all services for 100% production mode on local ports

echo ========================================
echo   AlphaMarkA Production Startup
echo ========================================
echo.

REM Set production mode
set PAPER_TRADING_MODE=false

REM Clean ports
echo [1/4] Cleaning ports...
call .\port_cleanup.bat
echo.

REM Start Redis
echo [2/4] Starting Redis...
docker run -d -p 6379:6379 --name alpha-redis redis:alpine
if %errorlevel% neq 0 (
    echo Redis container already exists or failed to start
    docker start alpha-redis
)
echo.

REM Wait for Redis to be ready
echo [3/4] Waiting for Redis to be ready...
timeout /t 3 /nobreak > nul
echo.

REM Start Dashboard
echo [4/4] Starting Dashboard on localhost:3000...
start "AlphaMark Dashboard" cmd /k "cd /d c:\Users\op\Desktop\alphamarkA && node frontend\server-local-production.js"
timeout /t 2 /nobreak > nul
echo.

REM Start Bot (Orchestration Bridge)
echo [5/5] Starting Trading Bot (Orchestration Bridge)...
start "AlphaMark Bot" cmd /k "cd /d c:\Users\op\Desktop\alphamarkA && set PAPER_TRADING_MODE=false && python execution_bot\scripts\bot.py"
echo.

echo ========================================
echo   System Started Successfully!
echo ========================================
echo.
echo Dashboard: http://localhost:3000
echo Mode: LIVE Trading (PAPER_TRADING_MODE=false)
echo.
echo To monitor trades, run:
echo powershell "Get-Content trade_history.csv -Tail 10 -Wait"
echo.
echo To stop all services:
echo docker stop alpha-redis
echo taskkill /FI "WindowTitle eq AlphaMark*"
echo.
pause
