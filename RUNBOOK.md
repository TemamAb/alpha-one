# AlphaMark Operational Runbook

**Version:** 1.0
**Environment:** Production (Fly.io)
**App Name:** `alpha`

---

## 🚨 Overview

This document contains standard operating procedures (SOPs) for managing the AlphaMark arbitrage application. Follow these procedures to ensure system stability, security, and operational consistency.

**Primary Contact:** Lead Orchestrator

---

## 0. Prerequisites

### 0.1. Install Fly.io CLI (`flyctl`)

Before running any `fly` commands, you must have the command-line tool installed.

```bash
# Run this command once to install flyctl
curl -L https://fly.io/install.sh | sh
```
**Note:** After installation, you may need to restart your terminal or add the `flyctl` directory to your system's PATH. The installer script provides instructions.

---

## 1. Routine Health Checks

Perform these checks daily or after any deployment.

### 1.1. Check Application Status

Verify that the application's virtual machines are running and passing health checks.

```bash
# Get a high-level overview of the app's status and VMs
fly status
```

**Expected Outcome:**
The `app` and `bot` processes should be in a `running` state. Health checks should be `passing`.

### 1.2. Check API Health Endpoint

Directly query the health check endpoint to ensure the backend server is responsive and the bot is communicating.

```bash
# Get the application's hostname
APP_URL=$(fly status --json | jq -r .Hostname)

# Query the health endpoint
curl "https://${APP_URL}/api/health"
```

**Expected Outcome:**
A JSON response with `{"status":"ok", "engine":"RUNNING", ...}`. If the engine status is `STOPPED` or `PAUSED`, it should match the intended state. A `503` error indicates a critical failure (e.g., Redis is down or the bot process is unresponsive).

### 1.3. Verify Profit Generation (Audit)

Filter the live logs for the specific cryptographic signature of a successful trade.

```bash
# Search for the "Success" signature in logs
fly logs | grep "✅ Arb submitted"
```

**Expected Outcome:**
Log lines like: `✅ Arb submitted! Profit: 0.045 ETH. Hash: 0x123...`

---

## 2. Logging and Debugging

### 2.1. View Live Logs

Stream logs from all running processes to monitor real-time activity. The logs are in JSON format for easy parsing.

```bash
# Stream logs from all processes
fly logs

# Stream logs from only the bot process
fly logs --process-group bot
```

---

## 3. Application Lifecycle Management

### 3.1. Restart the Application

To apply a configuration change or recover from a hung state, restart the application.

```bash
# Restart all VMs for the application
fly apps restart alpha
```

### 3.2. Rollback to a Previous Version

If a new deployment introduces a critical bug, roll back to a previously stable version.

```bash
# List recent releases to find a stable version number
fly releases

# Deploy a specific, previously successful release
fly deploy --image <image-tag-from-releases-list>
```

---

## 4. Configuration & Secrets Management

### 4.1. Update a Secret

Update an environment variable, such as an RPC endpoint or API key. The application will restart automatically to apply the change.

```bash
# Example: Update the Ethereum RPC endpoint
fly secrets set ETHEREUM_RPC="https://new-rpc-endpoint.com"
```

---

## 5. 🚨 Emergency Procedures 🚨

### 5.1. Activate the Emergency Kill Switch

This is the fastest way to halt all trading activity if the bot is behaving erratically. This command sets the Redis key that all worker processes check before every action.

```bash
# SSH into the running machine to access the fly-redis CLI
fly ssh console

# Inside the SSH session, connect to Redis and set the kill switch
redis-cli -u <your-redis-url> SET "alphamark:kill_switch" "true"

# Exit the SSH session
exit
```

**Note:** The dashboard's "Emergency Stop" button sets a different key (`EMERGENCY_STOP`). The command above sets the key (`alphamark:kill_switch`) that the Python workers are hardcoded to check, making it the most reliable manual override.