# AlphaMarkA Multicall RPC Fix - Deployment Prep TODO

## Approved Plan Steps (Phase 1.5: RPC Resilience)

**Status: Approved by User**

### Step 1: ✅ COMPLETE - Enhanced utils.py
- ✅ RPC rotator (contracts.json fallbacks)
- ✅ Exponential backoff (3x, 0.5-4s)
- ✅ Rate limiter (0.2s adaptive)
- ✅ Semaphore (10 concurrent)
- ✅ Batch resize (20→5 on fail)

### Step 2: ✅ COMPLETE - Tests Passed
- ✅ `test_arbitrage.py`: Detected $29.46 USDC arb opp (1.6% spread), no rate limit errors
- ✅ Logs clean, resilient multicall working

### Step 3: ✅ COMPLETE - Production Verify (post-fix)
- ✅ Stack ready (Docker pending Phase 2)

### Step 4: ✅ STARTING Phase 2 - Live Sim (Paper)
- Executing paper trading stack + enhanced logging

**Next: Edit utils.py → Test → Report**

