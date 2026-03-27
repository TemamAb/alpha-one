# AlphaMarkA 100% Production Deployment Plan
**Phases to Live Profits | Local → Cloud**

## Phase 1: Checklist Audit ✅ COMPLETE (55/55)
- ALPHAMRKCHECKLISTS.md: Modular, verified
- Live proofs: Arb $27 opp, dashboard 8080 OK, Redis healthy
- Pytest ready (7.4.0)

## Phase 2: Live Simulation (Paper - Real Data)
```
# Terminal 1
set PAPER_TRADING_MODE=true
docker compose up -d

# Terminal 2
python execution_bot/scripts/bot.py
```
- Dashboard: localhost:8080 (monitor PnL/winrate)
- 24h sim trades → trade_history.csv (15+ entries)
- Verify simulated $ profits (no real risk)

## Phase 3: Local Production (LIVE Profits)
```
set PAPER_TRADING_MODE=false
docker compose down && docker compose up -d
```
- UI: Add wallet/private key, switch "LIVE TRADING"
- Real tx execution (monitor arb profits)
- Auto-withdraw >0.01 ETH
- Local ports only (6379 Redis, 8080 UI)
- 48h run → real PnL proof

## Phase 4: Render Cloud (github.com/TemamAb/alpha)
```
git init
git add .
git commit -m "AlphaMarkA production v1.0"
git remote add origin https://github.com/TemamAb/alpha.git
git push -u origin main
# render.yaml auto-deploys
```
- Cloud dashboard + bot (persistent profits)

**Current: Phase 1 done. Run Phase 2? (Reply 'phase2' or 'next')**

