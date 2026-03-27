# AlphaMark Production Deployment Instructions

## Deployment Status: Ready for Production

### Quick Deploy (Recommended)

The fastest way to deploy AlphaMark to Render is through GitHub:

1. **Push to GitHub**
   ```bash
   git add -A
   git commit -m "chore: Production deployment"
   git push -u origin main
   ```

2. **Connect to Render**
   - Go to https://dashboard.render.com
   - Click "New" → "Blueprint"
   - Select your GitHub repository (alpha-one)
   - Select `render.yaml` as the blueprint file

3. **Add Secrets in Render Dashboard**
   Navigate to each service settings and add these environment variables:

   **Dashboard Service (alphamark-dashboard)**
   - `DASHBOARD_USER`: Your dashboard username
   - `DASHBOARD_PASS`: Your dashboard password  
   - `OPENAI_API_KEY`: Your OpenAI API key

   **Bot Service (alphamark-bot)**
   - `PRIVATE_KEY`: Your wallet private key
   - `WALLET_ADDRESS`: 0x748Aa8ee067585F5bd02f0988eF6E71f2d662751
   - `PIMLICO_API_KEY`: pim_UbfKR9ocMe5ibNUCGgB8fE
   - `FLASHLOAN_CONTRACT_ADDRESS`: Deployed contract address
   - `OPENAI_API_KEY`: Your OpenAI API key
   - `REDIS_URL`: Your Upstash connection string

### Alternative: Manual CLI Deploy

If you have Render CLI installed:

```bash
# Install CLI (requires Render account)
npm install -g render-cli

# Login
render login

# Deploy blueprint
render blueprints deploy render.yaml
```

### Production Configuration

The [`render.yaml`](render.yaml) blueprint deploys:

1. **alphamark-dashboard** - Web service (port 3000)
   - Health check: `/api/health`
   - Auto-restart on failures

2. **alphamark-bot** - Background worker
   - Runs arbitrage engine 24/7
   - Connects to production RPCs

3. **alpha-redis** - Managed Redis
   - IPC backbone for data sharing
   - Free tier

### Production RPCs Configured

- Ethereum: https://eth.llamarpc.com
- Polygon: https://polygon-rpc.com
- Arbitrum: https://arb1.arbitrum.io/rpc
- BSC: https://bsc-dataseed1.binance.org
- Optimism: https://mainnet.optimism.io
- Base: https://mainnet.base.org

### Important Notes

1. **LIVE TRADING MODE** is enabled by default (`PAPER_TRADING_MODE=false`)
2. **FlashLoan Contract** must be deployed before bot can execute trades
3. **Wallet** must have sufficient ETH for gas on target chains
4. **AAVE V3 Pool**: 0x87870Bca3F3fD6335C3F4c8392D7A5D3f4c4C5E (Ethereum)

### Post-Deployment Verification

Check logs after deployment:
```bash
render logs alphamark-dashboard
render logs alphamark-bot
```

Verify health endpoint:
```bash
curl https://alphamark-dashboard.onrender.com/api/health