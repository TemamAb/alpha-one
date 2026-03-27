# AlphaMark

AlphaMark is a multi-service arbitrage platform with a Python strategy/execution stack, a Node dashboard, Redis-backed control/telemetry, and Solidity flash-loan contracts.

## Status

Current repo state as of 2026-03-26:

- `20` active chains in the production config
- `23` configured DEX integrations in live stats
- active dashboard: `frontend/professional-dashboard.html`
- active web server: `frontend/server-dashboard.js`
- active bot runtime: `execution_bot/scripts/bot.py`
- active strategy runtime: `strategy_engine/src/strategy.py`
- active Render blueprint: `render.yaml`

This is not a proof of guaranteed profitability. The stack is production-runnable, but live profitability still depends on market conditions, RPC quality, working factory/router data, gas, slippage, and execution success.

## Architecture

The live stack is split into three services:

- Dashboard web service: Node/Express app serving the professional dashboard and APIs
- Bot worker: Python orchestrator, scanner, execution services
- Redis / Key Value: shared control plane and telemetry transport

Core files:

- [frontend/server-dashboard.js](/c:/Users/op/Desktop/alphamarkA/frontend/server-dashboard.js)
- [frontend/professional-dashboard.html](/c:/Users/op/Desktop/alphamarkA/frontend/professional-dashboard.html)
- [execution_bot/scripts/bot.py](/c:/Users/op/Desktop/alphamarkA/execution_bot/scripts/bot.py)
- [execution_bot/scripts/alpha_engine.py](/c:/Users/op/Desktop/alphamarkA/execution_bot/scripts/alpha_engine.py)
- [execution_bot/scripts/orchestrator.py](/c:/Users/op/Desktop/alphamarkA/execution_bot/scripts/orchestrator.py)
- [execution_bot/scripts/executor.py](/c:/Users/op/Desktop/alphamarkA/execution_bot/scripts/executor.py)
- [strategy_engine/src/strategy.py](/c:/Users/op/Desktop/alphamarkA/strategy_engine/src/strategy.py)
- [strategy_engine/src/utils.py](/c:/Users/op/Desktop/alphamarkA/strategy_engine/src/utils.py)
- [config_asset_registry/data/contracts.json](/c:/Users/op/Desktop/alphamarkA/config_asset_registry/data/contracts.json)

## Live Coverage

Integrated chains:

- `ethereum`
- `polygon`
- `bsc`
- `arbitrum`
- `optimism`
- `base`
- `avalanche`
- `linea`
- `scroll`
- `zksync_era`
- `blast`
- `manta_pacific`
- `mode`
- `zora`
- `gnosis`
- `fantom`
- `celo`
- `mantle`
- `berachain`
- `sei_evm`

Configured DEX coverage is surfaced live from `/api/stats` under `dexCoverage`.

Important operational distinction:

- Some chains are fully graph-scanning with working static or dynamic graphs
- Some chains are active only in monitor-first or thin static-graph mode
- Some chains still degrade due to RPC quality or missing validated factories

## Production Reality

What is working now:

- Start/stop/pause control from the dashboard
- live/paper mode propagation through Redis control state
- measured scan latency in live stats
- measured RPC latency in live stats
- per-chain scan diagnostics in live stats
- `20 / 20` chain coverage in the dashboard
- `23` configured DEX integrations in the dashboard

What is not proven:

- sustained profitable live execution
- guaranteed opportunity discovery on every chain
- guaranteed real profit transfer in every runtime condition

## Local Run

Requirements:

- Docker Desktop or compatible Docker engine
- Python 3.11+
- Node 18+
- valid `.env` with real RPCs, wallet, contract, and API keys

Start locally:

```bash
docker compose up -d --build
```

Dashboard:

- `http://localhost:8080`

Health:

- `http://localhost:8080/api/health`

Live stats:

- `http://localhost:8080/api/stats`

## Key APIs

- `GET /api/health`
- `GET /api/stats`
- `POST /api/control/start`
- `POST /api/control/pause`
- `POST /api/control/stop`
- `POST /api/bot/update`
- `GET /api/wallet/balance`

## Render Deployment

Render deployment is now based on a split-service blueprint in [render.yaml](/c:/Users/op/Desktop/alphamarkA/render.yaml):

- `alphamark-dashboard`: Docker web service using [frontend/Dockerfile](/c:/Users/op/Desktop/alphamarkA/frontend/Dockerfile)
- `alphamark-bot`: Docker worker using [Dockerfile.bot](/c:/Users/op/Desktop/alphamarkA/Dockerfile.bot)
- `alpha-redis`: Render Key Value service

Required Render secrets:

- `PRIVATE_KEY`
- `WALLET_ADDRESS`
- `DEPLOYER_ADDRESS`
- `PIMLICO_API_KEY`
- `FLASHLOAN_CONTRACT_ADDRESS`
- `OPENAI_API_KEY` if Copilot is required

Render worker RPC env vars currently wired in [render.yaml](/c:/Users/op/Desktop/alphamarkA/render.yaml) and expected for live deployment:

- `ETH_RPC_URL`
- `POLYGON_RPC_URL`
- `BSC_RPC_URL`
- `ARBITRUM_RPC_URL`
- `OPTIMISM_RPC_URL`
- `BASE_RPC_URL`
- `AVALANCHE_RPC_URL`
- `LINEA_RPC_URL`
- `SCROLL_RPC_URL`
- `ZORA_RPC_URL`
- `GNOSIS_RPC_URL`
- `FANTOM_RPC_URL`
- `CELO_RPC_URL`
- `MANTLE_RPC_URL`
- `BERACHAIN_RPC_URL`
- `MODE_RPC_URL`
- `BLAST_RPC_URL`
- `SEI_RPC_URL`

Additional chains in the top-20 registry such as `zksync_era` and `manta_pacific` are active in the current production config, but their cloud deployment handling may still rely on fallback or monitor-first paths until dedicated env wiring and chain-specific validation are added.

Live mode on Render is controlled with:

```text
PAPER_TRADING_MODE=false
```

## Strategy Notes

The strategy engine currently supports:

- dynamic graph building from V2-style factories where configured
- static router-based fallback graphs
- cross-chain monitor-only spread detection
- dynamic profit thresholds
- liquidity and ROI filters
- scan diagnostics by chain

Useful analysis tools:

- [analyze_graph_build.py](/c:/Users/op/Desktop/alphamarkA/analyze_graph_build.py)
- [PRODUCTION_UPGRADE_PLAN_2026-03-26.md](/c:/Users/op/Desktop/alphamarkA/PRODUCTION_UPGRADE_PLAN_2026-03-26.md)
- [CHAIN_ONBOARDING_CHECKLIST.md](/c:/Users/op/Desktop/alphamarkA/CHAIN_ONBOARDING_CHECKLIST.md)
- [KPI_COMPARISON.md](/c:/Users/op/Desktop/alphamarkA/KPI_COMPARISON.md)

## Safety

This repository can be configured to trade real funds.

Before any live deployment:

- verify the wallet and private key are correct
- verify the flash-loan contract address is correct
- verify per-chain RPC endpoints are not placeholders
- verify Redis is reachable
- verify dashboard start controls work as expected
- verify paper mode first where practical

Do not treat dashboard uptime, chain count, or DEX count as proof of profitability.
