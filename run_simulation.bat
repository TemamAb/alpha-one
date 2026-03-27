@echo off
echo AlphaMarkA Live Simulation - PAPER TRADING MODE
set PAPER_TRADING_MODE=true

echo [1/2] Starting Docker stack...
docker compose up -d

echo [2/2] Starting bot...
python execution_bot/scripts/bot.py

echo Simulation running...
echo Dashboard: http://localhost:8080
echo Logs live above. Ctrl+C to stop.
echo Verify: python verify_production.py
pause
