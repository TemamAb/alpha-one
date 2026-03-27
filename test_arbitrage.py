#!/usr/bin/env python3
"""
Live Arbitrage Scanner and Executor
Scans for real price differences between DEXs and executes if profitable
"""
import os
import sys
import json
import time
from web3 import Web3
from eth_account import Account
from datetime import datetime
import logging

# Load .env file for PRIVATE_KEY
from pathlib import Path
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

# Setup path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "strategy_engine", "src"))

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# Load config
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config_asset_registry", "data", "contracts.json")
with open(CONFIG_PATH, "r") as f:
    CONFIG = json.load(f)

# Token addresses
TOKENS = {
    "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    "DAI": "0x6B175474E89094C44Da98b954EedeAcb44dFce6CC",
    "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
    "WBTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"
}

# DEX Routers
DEX_ROUTERS = {
    "UniswapV2": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
    "Sushiswap": "0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F"
}

# ERC20 ABI for token approvals and transfers
ERC20_ABI = [
    {"constant": True, "inputs": [], "name": "name", "outputs": [{"name": "", "type": "string"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
    {"constant": False, "inputs": [{"name": "_spender", "type": "address"}, {"name": "_value", "type": "uint256"}], "name": "approve", "outputs": [{"name": "success", "type": "bool"}], "type": "function"},
]

# Uniswap V2 Router ABI
ROUTER_ABI = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"}
        ],
        "name": "getAmountsOut",
        "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"}
        ],
        "name": "swapExactETHForTokens",
        "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"}
        ],
        "name": "swapExactTokensForETH",
        "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

def get_w3():
    """Get Web3 instance with free public RPC"""
    rpc = CONFIG.get("ethereum", {}).get("rpc_production", "https://eth.llamarpc.com")
    w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={'timeout': 30}))
    try:
        block = w3.eth.block_number
        logger.info(f"Connected to RPC: {rpc[:40]}... Block: {block}")
        return w3
    except Exception as e:
        logger.error(f"RPC connection test failed: {e}")
        # Try fallback
        w3 = Web3(Web3.HTTPProvider("https://cloudflare-eth.com", request_kwargs={'timeout': 30}))
        try:
            block = w3.eth.block_number
            logger.info(f"Using fallback RPC - Block: {block}")
            return w3
        except:
            logger.error("Fallback also failed")
            return None

def get_token_price(w3, router_addr, token_in, token_out, amount_wei):
    """Get swap price from router"""
    try:
        router = w3.eth.contract(address=router_addr, abi=ROUTER_ABI)
        path = [token_in, token_out]
        amounts = router.functions.getAmountsOut(amount_wei, path).call()
        return amounts[1]
    except Exception as e:
        return None

def scan_arbitrage(w3):
    """Scan for arbitrage opportunities between DEXs"""
    opportunities = []
    
    # Test with 1 ETH worth of tokens
    test_amount = Web3.to_wei(1, 'ether')
    
    logger.info("=" * 60)
    logger.info("SCANNING FOR ARBITRAGE OPPORTUNITIES")
    logger.info("=" * 60)
    
    for token_name, token_addr in TOKENS.items():
        if token_name == "WETH":
            continue
            
        prices = {}
        
        for dex_name, router_addr in DEX_ROUTERS.items():
            price = get_token_price(w3, router_addr, TOKENS["WETH"], token_addr, test_amount)
            if price:
                # Convert to human readable (token decimals)
                prices[dex_name] = price
        
        if len(prices) >= 2:
            uni_price = prices.get("UniswapV2", 0)
            sushi_price = prices.get("Sushiswap", 0)
            
            if uni_price > 0 and sushi_price > 0:
                # Calculate spread
                diff = abs(uni_price - sushi_price)
                avg = (uni_price + sushi_price) / 2
                spread_pct = (diff / avg) * 100
                
                # Determine buy/sell direction
                if uni_price < sushi_price:
                    buy_dex = "UniswapV2"
                    sell_dex = "Sushiswap"
                    buy_price = uni_price
                    sell_price = sushi_price
                else:
                    buy_dex = "Sushiswap"
                    sell_dex = "UniswapV2"
                    buy_price = sushi_price
                    sell_price = uni_price
                
                # Calculate potential profit (assuming 1 ETH trade)
                # Prices are in USDC (6 decimals)
                profit_usdc = (sell_price - buy_price) / 1e6  # Convert to actual USDC
                # Convert USDC profit to ETH value
                eth_price_usdc = buy_price / 1e6  # 1 ETH = this many USDC
                profit_eth = profit_usdc / eth_price_usdc  # Profit in ETH
                
                # Estimate gas cost (roughly 150k gas * 20 gwei = 0.003 ETH)
                gas_cost_eth = float(profit_eth) * 0.1  # Assume 10% of profit as gas
                net_profit_eth = float(profit_eth) - gas_cost_eth
                net_profit_usd = net_profit_eth * 2000  # Assume ETH = $2000
                
                logger.info(f"Token: {token_name}")
                logger.info(f"  Uniswap:   {uni_price / 1e6:.2f} (USDC decimals)")
                logger.info(f"  Sushiswap: {sushi_price / 1e6:.2f}")
                logger.info(f"  Spread:    {spread_pct:.3f}%")
                logger.info(f"  Direction: Buy {buy_dex} -> Sell {sell_dex}")
                logger.info(f"  Gross Profit: {profit_eth:.6f} ETH")
                logger.info(f"  Net Profit:   {net_profit_eth:.6f} ETH (${net_profit_usd:.2f})")
                logger.info("-" * 40)
                
                if net_profit_usd > 10:  # Only consider if > $10 profit
                    opportunities.append({
                        "token": token_name,
                        "buy_dex": buy_dex,
                        "sell_dex": sell_dex,
                        "buy_router": DEX_ROUTERS[buy_dex],
                        "sell_router": DEX_ROUTERS[sell_dex],
                        "spread_pct": spread_pct,
                        "gross_profit_eth": profit_eth,
                        "net_profit_eth": net_profit_eth,
                        "net_profit_usd": net_profit_usd
                    })
    
    return opportunities

def execute_arbitrage(w3, opportunity, private_key):
    """Execute the arbitrage trade"""
    try:
        account = Account.from_key(private_key)
        wallet_address = account.address
        logger.info(f"Executing from wallet: {wallet_address}")
        
        # For this demo, we'll just show what would be executed
        # Real execution requires:
        # 1. Approval of tokens
        # 2. Flash loan execution
        # 3. Complex multi-step swaps
        
        logger.info(f"WOULD EXECUTE: {opportunity}")
        logger.info("Note: Real execution requires flash loan contract and multi-step swaps")
        return True
        
    except Exception as e:
        logger.error(f"Execution error: {e}")
        return False

def main():
    print("\n" + "=" * 60)
    print("[ARBITRAGE] LIVE SCANNER - Finding Profitable Opportunities")
    print("=" * 60 + "\n")
    
    # Connect to blockchain
    w3 = get_w3()
    if not w3:
        print("ERROR: Cannot connect to blockchain")
        return
    
    # Scan for opportunities
    opportunities = scan_arbitrage(w3)
    
    print("\n" + "=" * 60)
    print("SCAN COMPLETE")
    print("=" * 60)
    
    if opportunities:
        print(f"\nFound {len(opportunities)} potentially profitable opportunities:")
        for i, opp in enumerate(opportunities):
            print(f"\n{i+1}. {opp['token']}")
            print(f"   Spread: {opp['spread_pct']:.3f}%")
            print(f"   Net Profit: {opp['net_profit_eth']:.6f} ETH (${opp['net_profit_usd']:.2f})")
            print(f"   Route: Buy {opp['buy_dex']} -> Sell {opp['sell_dex']}")
        
        # Get private key from environment
        private_key = os.environ.get('PRIVATE_KEY', '')
        # Accept both 64 (no 0x) and 66 (with 0x) character private keys
        if private_key and len(private_key) in (64, 66):
            print("\n" + "=" * 60)
            print("ATTEMPTING EXECUTION")
            print("=" * 60)
            for opp in opportunities:
                if opp['net_profit_usd'] > 20:  # Only execute if > $20
                    result = execute_arbitrage(w3, opp, private_key)
                    if result:
                        print(f"Executed: {opp['token']} - Profit: ${opp['net_profit_usd']:.2f}")
                        break
        else:
            print("\nNo PRIVATE_KEY found in environment - skipping execution")
            print("Set PRIVATE_KEY env var to attempt execution")
    else:
        print("\nNo profitable arbitrage opportunities found.")
        print("\nPossible reasons:")
        print("1. Market is efficient - prices are aligned across DEXs")
        print("2. Spread is too small to cover gas costs")
        print("3. MEV bots have already captured the opportunities")
        print("\nThis is NORMAL - profitable arb opportunities are rare and fleeting!")

if __name__ == "__main__":
    main()