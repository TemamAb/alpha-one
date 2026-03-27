# Power-Up Script for AlphaMark (Windows Native)
$ErrorActionPreference = "Stop"

Write-Host "🚀 RESUMING MISSION: LIVE PROFIT GENERATION" -ForegroundColor Cyan

# 1. Force Environment Variables (Live Mode)
$env:PAPER_TRADING_MODE = "false"
$env:NETWORK = "localethereum"

Write-Host "   Target Network: $env:NETWORK"
Write-Host "   Trading Mode:   LIVE (Real Funds)" -ForegroundColor Red

# 2. Deploy Contract
Push-Location smart_contracts
try {
    Write-Host "`n📡 Step 1: Deploying FlashLoan Contract..." -ForegroundColor Yellow
    # Use cmd /c npx to avoid PowerShell execution policy issues with node modules
    $deployOutput = cmd /c npx hardhat run scripts/deploy.js --network $env:NETWORK 2>&1
    
    # Print output for visibility
    $deployOutput | ForEach-Object { Write-Host $_ }

    # Capture address using regex
    if ($deployOutput -match "FlashLoan deployed to:\s+(0x[a-fA-F0-9]{40})") {
        $contractAddr = $matches[1]
        Write-Host "✅ Contract Deployed: $contractAddr" -ForegroundColor Green
        $env:FLASHLOAN_CONTRACT_ADDRESS = $contractAddr
    } else {
        Write-Warning "⚠️  Could not auto-capture contract address. Check output above."
    }
} catch {
    Write-Error "❌ Deployment failed. Ensure local Hardhat node is running (port 8545)."
    exit 1
} finally {
    Pop-Location
}

# 3. Start Execution Bot
Write-Host "`n🤖 Step 2: Starting Execution Bot..." -ForegroundColor Yellow
python execution_bot/scripts/bot.py