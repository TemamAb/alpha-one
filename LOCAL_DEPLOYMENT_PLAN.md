# AlphaMark Local Deployment Plan (Phase 1)
## For Profit Generation in Local Simulation Mode

**Objective:** Deploy AlphaMark to local ports to generate profit in simulation mode  
**Approval Status:** PENDING USER APPROVAL  
**Execution:** Will NOT start until you approve

---

## Understanding the Local Profit Generation Model

Since we're deploying to **local ports (localhost)**, we need to create a self-contained arbitrage environment:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    LOCAL PROFIT GENERATION MODEL                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐       │
│  │  Local Geth  │      │  Local Geth   │      │  Local Geth  │       │
│  │  (Ethereum)  │      │  (Polygon)    │      │    (BSC)     │       │
│  │  Port:8545   │      │  Port:8546    │      │  Port:8547   │       │
│  └──────────────┘      └──────────────┘      └──────────────┘       │
│         │                      │                      │                │
│         └──────────────────────┼──────────────────────┘                │
│                                ▼                                       │
│                    ┌──────────────────────┐                            │
│                    │   AlphaMark System   │                            │
│                    │  • Strategy Engine   │                            │
│                    │  • Execution Bot    │                            │
│                    │  • Risk Management  │                            │
│                    └──────────────────────┘                            │
│                                │                                       │
│                                ▼                                       │
│                    ┌──────────────────────┐                            │
│                    │   Profit Generation  │                            │
│                    │   (Simulated Arb)    │                            │
│                    └──────────────────────┘                            │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Step-by-Step Implementation Plan

### STEP 1: Set Up Local Blockchain Networks (Required Prerequisites)

We need 3 local blockchain nodes running simultaneously:

| Chain | RPC Port | WebSocket Port | Purpose |
|-------|----------|-----------------|---------|
| Ethereum | 8545 | 8546 | Primary chain |
| Polygon | 8547 | 8548 | Secondary chain |
| BSC | 8549 | 8550 | Tertiary chain |

**Action Required:**
```bash
# Option A: Using Hardhat (Recommended)
# Start 3 hardhat nodes in separate terminals

# Terminal 1 - Ethereum Mainnet Fork
npx hardhat node --port 8545

# Terminal 2 - Polygon Fork  
npx hardhat node --port 8547

# Terminal 3 - BSC Fork
npx hardhat node --port 8549
```

---

### STEP 2: Fix Configuration Files for Local Mode

**File:** `flashloan_app/config_asset_registry/data/contracts.json`

```json
{
  "ethereum": {
    "rpc": "http://127.0.0.1:8545",
    "ws": "ws://127.0.0.1:8546",
    "chain_id": 1,
    "lending_pool": "0x87870Bca3F3fD6335C3F4c8392D7A5D3f4c4C5E",  // Aave V3 Eth
    "dexes": {
      "uniswap_v2": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
      "uniswap_v3": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
      "sushiswap": "0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F"
    },
    "tokens": {
      "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
      "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
      "DAI": "0x6B175474E89094C44Da98b954EesadcdEF9ce6CC"
    }
  },
  "polygon": {
    "rpc": "http://127.0.0.1:8547",
    "ws": "ws://127.0.0.1:8548",
    "chain_id": 137,
    "lending_pool": "0x794a61358D6845594F94dc1DB02A252b5b4814aD",
    "dexes": {
      "quickswap": "0xa5E0829CaCEd8fFDD4De3c43696c57F7d7A678ff",
      "sushiswap": "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506"
    },
    "tokens": {
      "USDC": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
      "WMATIC": "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270"
    }
  },
  "bsc": {
    "rpc": "http://127.0.0.1:8549",
    "ws": "ws://127.0.0.1:8550",
    "chain_id": 56,
    "lending_pool": "0x4F628a66Db8a0537D7147bC8Db7d8EA1F5Aa6f6",
    "dexes": {
      "pancakeswap_v2": "0x10ED43C718714eb63d5aA57B78B54704E256024E",
      "biswap": "0x3fC13D266e01AF74a7E8e6a34D5B0f5a5fAaCa5b"
    },
    "tokens": {
      "USDC": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
      "WBNB": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
    }
  }
}
```

---

### STEP 3: Deploy Smart Contracts to Local Networks

**Action Required:** Deploy FlashLoan.sol contracts to each local network

```bash
# Deploy to Ethereum local
npx hardhat run scripts/deploy.js --network localethereum

# Deploy to Polygon local
npx hardhat run scripts/deploy.js --network localpolygon

# Deploy to BSC local
npx hardhat run scripts/deploy.js --network localbsc
```

---

### STEP 4: Update Execution Bot for Local Mode

**File:** `flashloan_app/execution_bot/scripts/executor.py`

Changes needed:
- Use local RPC endpoints
- Use test private key (hardhat dev account)
- Implement real on-chain execution

---

### STEP 5: Update Strategy Engine for Real Prices

**File:** `flashloan_app/strategy_engine/src/utils.py`

Replace random price generator with:
- Real Uniswap/SushiSwap/QuickSwap router calls
- Price fetching from on-chain DEX pairs

---

### STEP 6: Update Liquidity Fetcher

**File:** `flashloan_app/market_data_aggregator/scripts/fetch_liquidity.py`

Replace hardcoded return with:
- Real pair reserve fetching from DEX factories
- Real-time liquidity monitoring

---

### STEP 7: Configure Local Mempool Monitor

**File:** `flashloan_app/mempool_mev/scripts/mempool_monitor.py`

Update WebSocket URLs to local network WebSocket endpoints

---

### STEP 8: Start the Bot

```bash
# Terminal 4 - Start AlphaMark Bot
cd flashloan_app
python execution_bot/scripts/bot.py
```

---

## Port Configuration Summary

| Service | Port | Protocol |
|---------|------|----------|
| Ethereum Local RPC | 8545 | HTTP |
| Ethereum Local WS | 8546 | WebSocket |
| Polygon Local RPC | 8547 | HTTP |
| Polygon Local WS | 8548 | WebSocket |
| BSC Local RPC | 8549 | HTTP |
| BSC Local WS | 8550 | WebSocket |
| Monitoring Dashboard | 3000 | HTTP |
| Database (PostgreSQL) | 5432 | TCP |
| Redis Cache | 6379 | TCP |

---

## Pre-Execution Checklist

Before I execute, please confirm:

- [ ] I have Hardhat installed (`npm install -g hardhat`)
- [ ] I have Python 3.8+ with required packages
- [ ] I have at least 8GB RAM available
- [ ] Ports 8545-8550, 3000, 5432, 6379 are available
- [ ] I understand this is LOCAL simulation (not real mainnet)

---

## Execution Sequence (When Approved)

1. **Create local Hardhat network configurations**
2. **Update contracts.json with local RPCs**
3. **Update utils.py for real price feeds**
4. **Update fetch_liquidity.py for real liquidity**
5. **Update executor.py for local execution**
6. **Update mempool_monitor.py for local WebSockets**
7. **Deploy contracts to local networks**
8. **Start 3 local blockchain nodes**
9. **Fund test wallets with test tokens**
10. **Start the AlphaMark bot**
11. **Verify profit generation in dashboard**

---

## Expected Outcome

After successful deployment to local ports:
- ✅ Bot scans 3 local chains for arbitrage opportunities
- ✅ Executes real flash loans on local networks
- ✅ Generates simulated profit (visible in dashboard)
- ✅ Risk management checks operational
- ✅ All systems communicate properly

---

**STATUS: AWAITING YOUR APPROVAL TO EXECUTE**

Please reply with "APPROVED" or "I approve" to begin Phase 1 local deployment.

Or specify which steps you'd like modified before approval.
