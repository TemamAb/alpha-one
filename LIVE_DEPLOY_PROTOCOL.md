# AlphaMarkA LIVE Deployment Protocol (User Command: Direct Live Mode)

**Reconfigured:** Paper optional. Direct live as priority.

**Live Mode Steps (No Paper Gate):**
1. **Cloud Deploy:** Render/Fly auto w/ mainnet RPCs (contracts.json production).
2. **GitHub:** Pushed (eb0ad8e).
3. **Secrets:** Render UI sync=false (PRIVATE_KEY/WALLET/PIMLICO from .env).
4. **Live Trading:** PAPER_TRADING=false default.

**Commands:**
```
# Cloud
render deploy --file render.yaml  # or fly deploy
# Monitor
render logs alphamark-dashboard
```

**Status:** Direct live ready. Profits on deploy.
