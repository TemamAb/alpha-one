#!/bin/bash
export PAPER_TRADING_MODE=false
echo "[1/2] Docker up..."
docker compose up -d
echo "[2/2] Bot LIVE (real tx)..."
python execution_bot/scripts/bot.py
echo "Live @ localhost:8080"
echo "Real profits! Ctrl+C stop."
