# AlphaMark Render Live Trading Fix Plan
Status: 🔄 In Progress | Priority: 🚨 CRITICAL

## Phase 1: Fix Redis Connection (server-dashboard.js)
```
1. Update Redis client for Render KV (cluster mode):
   - Add `socket: { tls: true }`
   - Increase connectTimeout: 30000
   - Retry strategy with exponential backoff
2. Add health logging: console.log('[REDIS] Connection state:', redisClient.isOpen)
3. Test: Deploy → check logs for '[REDIS] Cluster link ESTABLISHED'
```

## Phase 2: Fix Bot Worker Startup (Dockerfile.bot)
```
1. Add ENTRYPOINT ["python", "-u", "execution_bot/scripts/bot.py"]
2. Ensure bot.py subscribes 'alphamark:control' channel
3. Add healthcheck: redis-cli ping
```

## Phase 3: Test Live Trading
```
1. Deploy fixes
2. Settings → Refresh Status → Verify REDIS_URL: [CONNECTED]
3. Start Engine → LIVE → Check worker logs for 'START' received
4. Monitor Live Trades tab
```

## Verification Commands
```
# Render Dashboard → Logs → Filter 'REDIS'
# curl https://dashboard.onrender.com/api/health
# Expected: {"engine":"RUNNING","redis":"connected"}
```

## Rollback
```
PAPER_TRADING_MODE=true (safe simulation)
```

