# AlphaMark Developer Guide: From Simulation to Profit

**Version:** 2.0 (Enterprise Architecture)
**Status:** Master Implementation Plan  
**Objective:** Achieve a production-ready, secure, and profitable gasless arbitrage system.

---

## 1. Introduction

### What is this guide?
This document is the canonical, step-by-step master plan for elevating the AlphaMark application from its current state—a sophisticated simulation—to a fully operational, live-trading, and profit-generating system on the blockchain.

### Why does it exist?
To eliminate ambiguity and provide a single source of truth for development. By following this phased approach, we ensure that every component is built to production-grade standards, security vulnerabilities are systematically addressed, and the path to profitability is clear, direct, and repeatable.

### How do we use it?
We will execute this plan phase by phase. Each task includes the **What** (the action), the **Why** (the strategic reason), and the **How** (the technical implementation). Do not proceed to the next phase until the current one is complete and verified.

---

## Phase 0: The Infrastructure Core (Prerequisites)

**Goal:** Deploy the immutable logic that allows the bot to interact with the blockchain.

### Task 0.1: Smart Contract Deployment
*   **What:** Deploy the `FlashLoan.sol` contract to the target chain (e.g., Polygon, Arbitrum).
*   **Why:** The Python bot is just a trigger; the Solidity contract holds the funds and executes the atomic trade logic. It must exist on-chain before the bot can target it.
*   **How:**
    1.  Use `hardhat` or `foundry` to deploy.
    2.  **Verify** the contract source code on the block explorer (PolygonScan/Etherscan).
    3.  **Update Config:** Add the new contract address to `contracts.template.json`.

### Task 0.2: Token Allowances
*   **What:** Approve the DEX Routers (Uniswap, SushiSwap) to spend tokens held by your Smart Account/Contract.
*   **Why:** Swaps will revert if the contract hasn't pre-approved the routers to move its tokens.
*   **How:** Write a "setup" script to approve `MAX_UINT256` for WETH, USDC, and DAI on all target Routers.

---

## Phase 1: Foundational Connectivity (The "Hello, Blockchain" Phase)

**Goal:** Eradicate all mocked data. Make the bot read real, live, on-chain data.

### Task 1.1: Unify and Sanitize Configuration

*   **What:** The `scripts/build_config.py` script now dynamically builds `contracts.json` from the `.env` file at build time.
*   **Why:** The current codebase has multiple `.env` files and a hardcoded `contracts.json` with `localhost` RPCs. This is the #1 cause of deployment failure and prevents any real blockchain communication.
*   **How:**
    1.  **Consolidate:** Maintain the single `.env` file at the project root.
    2.  **Verify Script:** Ensure `scripts/build_config.py` correctly reads `RPC_URL`s and injects them into `contracts.template.json`.
    3.  **Docker Integration:** The `Dockerfile` runs this script (`RUN python3 scripts/build_config.py`) to bake the config into the container image.

### Task 1.2: Enterprise I/O (Persistent Connections)

*   **What:** Use `requests.Session` with TCP Keep-Alive for all RPC calls.
*   **Why:** Eliminates SSL handshake overhead (~200ms) per call, reducing tick-to-trade latency to <20ms.
*   **How:**
    1.  **Session Pooling:** In `utils.py`, use a global `_W3_CACHE` to store Web3 providers initialized with a custom HTTP adapter.
    2.  **Connection Reuse:** Reuse these providers for `get_price` and `fetch_liquidity` calls.

### Task 1.3: Implement Real Liquidity Feeds

*   **What:** Replace the hardcoded `100000.0` in `fetch_liquidity.py` with a function that queries the actual reserves of a liquidity pool.
*   **Why:** Risk management is impossible without knowing a pool's real liquidity. A large trade in a small pool will cause massive slippage and lead to losses.
*   **How:**
    1.  **Target Pair Contracts:** Use `web3` to interact with the `getReserves` function on a Uniswap V2-style pair contract.
    2.  **Update `fetch_liquidity`:** Modify the function to take a pair address, connect to the contract, and return the `reserve0` and `reserve1` values.

### Task 1.4: The "Simulation Gate" (Critical Audit Requirement)
*   **What:** Implement an `eth_call` simulation before ever attempting to build a UserOperation.
*   **Why:** **Gas Griefing Protection.** Never send a transaction that hasn't been proven to succeed via simulation. If you send a failing transaction, you pay for the computation (even in gasless modes, the Paymaster may reject it, or you lose reputation).
*   **How:**
    1.  Use `web3.eth.call` (or `contract.functions.execute(...).call()`) to simulate the arbitrage transaction locally against the current block.
    2.  **Gatekeeper Logic:** If the simulation reverts or returns < `MIN_PROFIT`, abort immediately. Do not proceed to Phase 2.

---

## Phase 2: The Enterprise Execution Engine

**Goal:** Execute profitable transactions with high probability and capital efficiency.

### Task 2.1: Graph-Based Strategy Discovery

*   **What:** Use DFS (Depth-First Search) to dynamically discover profitable cycles (Graph Arb) instead of hardcoded lists.
*   **Why:** Finds non-obvious opportunities (e.g., WETH -> PEPE -> USDC -> WETH) that hardcoded strategies miss.
*   **How:**
    1.  **Build Graph:** Construct an adjacency list of tokens and pools.
    2.  **Traverse:** Recursively find all cycles of length 2 to `MAX_HOPS`.
    3.  **Simulate:** Check profitability of the entire path on-chain.

### Task 2.2: Advanced Gas Management (EIP-1559)

*   **What:** Dynamically calculate `maxFeePerGas` and `maxPriorityFeePerGas`.
*   **Why:** Static multipliers fail in volatile markets. Dynamic pricing ensures inclusion in the next block.
*   **How:**
    1.  **Fetch Base Fee:** Get `baseFeePerGas` from the latest block.
    2.  **Add Buffer:** Apply a 20% buffer + a generous `priorityFee` to outbid competitors.

### Task 2.3: Atomic Nonce Pipelining (Redis)
*   **What:** Use Redis `INCR` to manage nonces instead of fetching from the chain.
*   **Why:** Enables high-velocity, concurrent execution by preventing nonce collisions between workers.
*   **How:**
    1.  **Initialize:** Fetch nonce from chain on startup.
    2.  **Increment:** Use Redis atomic increment for each new `UserOperation`.
    3.  **Fallback:** Retry if Redis is unavailable.

### Task 2.4: MEV Protection (Private Bundlers)
*   **What:** Route transactions to private bundlers (e.g., Flashbots, Titan).
*   **Why:** Prevents "Sandwich Attacks" where bots front-run your trade and steal the profit.
*   **How:**
    1.  **Configure:** Set `MEV_PROTECTION=true` and provide private bundler URLs in `.env`.
    2.  **Route:** `executor.py` logic switches destination based on this flag.

---

### Task 2.5: Concurrent Execution Engine
*   **What:** Multi-process architecture with `Scanner` and `Executor` workers.
*   **Why:** Decouples scanning from execution, allowing 100% uptime on opportunity detection.
*   **How:**
    1.  **Scanner Process:** Dedicated loop running `find_graph_arbitrage_opportunities`.
    2.  **Queue:** `multiprocessing.Queue` to buffer opportunities.
    3.  **Executor Pool:** Multiple workers consuming from the queue and executing via `executor.py`.

---

## Phase 3: Production Hardening & Security

**Goal:** Make the system secure, resilient, and observable.

### Task 3.1: Secure Secrets Management

*   **What:** Move the `PRIVATE_KEY` and all API keys out of the `.env` file and into a secure secrets manager.
*   **Why:** Committing secrets to a repository, even in an ignored `.env` file, is a critical security failure. An accidental `git add -f` could expose all funds.
*   **How:**
    1.  **Use Fly.io Secrets:** For the Fly.io deployment, use the `flyctl` CLI to set secrets.
        ```bash
        fly secrets set PRIVATE_KEY="0x..." PIMLICO_API_KEY="..."
        ```
    2.  **Verify Code:** The application code already uses `os.environ.get()`, which will automatically and safely read these environment variables at runtime. No code changes are needed.

### Task 3.2: Implement Structured Logging

*   **What:** Convert all `print()` and `logging.info()` calls to output structured JSON logs.
*   **Why:** JSON logs are machine-readable. This allows for powerful searching, filtering, and dashboarding in a log management platform (like Fly.io's integrated logger or Datadog), which is impossible with plain text.
*   **How:**
    1.  **Use a JSON Formatter:** In `bot.py`, configure the root logger to use a custom `JSONFormatter`.

    ```python
    # In bot.py
    import json

    class JsonFormatter(logging.Formatter):
        def format(self, record):
            log_record = {
                "timestamp": self.formatTime(record, self.datefmt),
                "level": record.levelname,
                "message": record.getMessage(),
                # Add other fields from the log record as needed
            }
            return json.dumps(log_record)

    # In main configuration
    logHandler = logging.StreamHandler()
    logHandler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[logHandler])
    ```

### Task 3.3: Add Robust Health Checks

*   **What:** Enhance the `/api/health` endpoint to be a true indicator of application health.
*   **Why:** The deployment environment (Fly.io) uses this endpoint to determine if the application is healthy. A failing check will trigger an automatic restart, preventing zombie processes.
*   **How:**
    1.  **Update `server-dashboard.js`:** Modify the `/api/health` endpoint to check the `lastUpdate` timestamp from `botStats`.
    2.  **Set a Threshold:** If `Date.now() - botStats.lastUpdate` is greater than a threshold (e.g., 60 seconds), return a `503 Service Unavailable` status. This indicates the bot has stopped communicating and the container is unhealthy.

### Task 3.4: The Kill Switch
*   **What:** A mechanism to instantly stop trading via an environment variable or dashboard button.
*   **Why:** If the bot encounters a bug that drains funds or spams the network, you must stop it within seconds, not minutes.
*   **How:**
    1.  **Redis Flag:** The bot checks a Redis key `EMERGENCY_STOP` at the start of every loop.
    2.  **Dashboard Integration:** Add a big red "STOP" button on the dashboard that sets this Redis key.
    3.  **Env Var Fallback:** If `os.environ.get("KILL_SWITCH") == "true"`, the bot process terminates immediately.

---

## Phase 4: Deployment & Operations

**Goal:** Achieve a repeatable, reliable deployment process and operational visibility.

### Task 4.1: Finalize `fly.toml` Configuration

*   **What:** Define the application's services, ports, health checks, and scaling rules for Fly.io.
*   **Why:** This file is the "recipe" Fly.io uses to deploy and run the application container. Incorrect configuration will lead to deployment failure or improper runtime behavior.
*   **How:**
    1.  **Define Health Check:** Add a `[[http_service.checks]]` section to `fly.toml` that points to the `/api/health` endpoint.
    2.  **Ensure Persistence:** Confirm that `auto_stop_machines` is set to `false`. This is **critical**. If true, Fly.io will shut down your machine when there is no web traffic, killing the background arbitrage bot.
    3.  **Set Resources:** Define appropriate CPU and memory (`shared-cpu-1x`, `1gb`) to ensure both the Node.js and Python processes can run without crashing.

    ```toml
    # In fly.toml
    [http_service]
      internal_port = 3000
      force_https = true
      auto_stop_machines = false # CRITICAL: Keep the bot running
      auto_start_machines = true
      min_machines_running = 1

    [[http_service.checks]]
      interval = "15s"
      timeout = "10s"
      grace_period = "30s" # Give time for the app to start
      method = "get"
      path = "/api/health"
    ```

### Task 4.2: Master the Deployment Workflow

*   **What:** Document and practice the exact sequence of commands for a successful deployment.
*   **Why:** A clear, repeatable process prevents costly mistakes during production updates.
*   **How:**
    1.  **First-Time Setup:**
        ```bash
        # Install the Fly.io CLI
        # Run from the project root
        fly launch --no-deploy
        ```
        *This command detects your `Dockerfile`, creates a `fly.toml`, and sets up the app on Fly.io without deploying yet.*

    2.  **Set All Secrets:**
        ```bash
        fly secrets set PRIVATE_KEY="0x..."
        fly secrets set PIMLICO_API_KEY="..."
        # ... set all other secrets from .env
        ```

    3.  **Deploy and Monitor:**
        ```bash
        # Deploy the application
        fly deploy

        # Monitor the live logs from all processes
        fly logs
        ```

### Task 4.3: Create an Operational Runbook

*   **What:** A simple markdown document (`RUNBOOK.md`) outlining procedures for common operational tasks.
*   **Why:** When an issue occurs at 3 AM, you need a checklist, not a memory test. A runbook saves time and prevents panic-induced errors.
*   **How:** Document the following procedures:
    *   **How to Check System Health:** `fly status` and `curl <app-url>/api/health`.
    *   **How to View Logs:** `fly logs`.
    *   **How to Restart the Application:** `fly apps restart alpha-tpijg`.
    *   **How to Rollback to a Previous Version:** `fly deploy --image <previous-image-tag>`.
    *   **How to Update a Secret:** `fly secrets set KEY=VALUE`.

---

## Conclusion

This guide provides the complete roadmap to transition AlphaMark into a production-grade, profitable system. By executing these phases methodically, we will build a robust, secure, and efficient arbitrage engine. The focus on real data, gasless execution, and operational hardening is paramount to long-term success.