@echo off
REM AlphaMarkA Production Startup Script
REM Run this in Windows Command Prompt or PowerShell

echo Starting AlphaMarkA Production System...

REM Set production mode
set PAPER_TRADING_MODE=false

REM Start Dashboard in background
echo Starting Dashboard on localhost:3000...
start "AlphaMark Dashboard" cmd /k "cd /d c:\Users\op\Desktop\alphamarkA && node frontend\server-local-production.js"

REM Wait a moment
timeout /t 3 /nobreak > nul

REM Start Bot
echo Starting Trading Bot...
start "AlphaMark Bot" cmd /k "cd /d c:\Users\op\Desktop\alphamarkA && set PAPER_TRADING_MODE=false && python execution_bot\scripts\bot.py"

echo.
echo System started!
echo Dashboard: http://localhost:3000
echo.
echo To monitor trades, run:
echo powershell "Get-Content trade_history.csv -Tail 10 -Wait"
pause