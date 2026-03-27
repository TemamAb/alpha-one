#!/usr/bin/env python3
"""
Live Blockchain Price Checker
Shows real-time prices from various DEXs on Ethereum to debug why no arbitrage is found.
"""
import os
import sys
import json
import logging
import requests

# Setup path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "strategy_engine", "src"))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# Load config
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config_asset_registry", "data", "contracts.json")
with open(CONFIG_PATH, "r") as f:
    CONFIG = json.load(f)

# Hardcoded token addresses
TOKEN_ADDRESSES = {
    "ethereum": {
        "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "DAI": "0x6B175474E89094C44Da98b954EedeAcb44dFce6CC",
        "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        "WBTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"
    },
    "polygon": {
        "WMATIC": "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",
        "USDC": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        "USDT": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F"
    }
}

# Uniswap V2 Router ABI (simplified for getAmountsOut)
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
    }
]

def get_rpc(chain):
    """Get RPC URL for chain - prefer production RPC"""
    if chain in CONFIG:
        # Try production RPC first
        if CONFIG[chain].get('rpc_production'):
            return CONFIG[chain]['rpc_production']
        # Fallback to local
        return CONFIG[chain].get('rpc', '')
    return ''

def get_router(chain):
    """Get router address for chain"""
    if chain in CONFIG:
        return CONFIG[chain].get('router_dex', '')
    return ''

def get_price(w3, router_address, token_in, token_out, amount=1000000):
    """Get price from router"""
    try:
        from web3 import Web3
        router = w3.eth.contract(address=router_address, abi=ROUTER_ABI)
        path = [token_in, token_out]
        amounts = router.functions.getAmountsOut(amount, path).call()
        # amount out in token_out decimals
        return amounts[1] / (10**18)  # Normalize to ETH equivalent
    except Exception as e:
        return None

def check_dex_price_diff(chain, dex_name, router_address, tokens):
    """Check for price differences between tokens"""
    from web3 import Web3
    
    rpc = get_rpc(chain)
    if not rpc:
        print(f"  [ERROR] No RPC for {chain}")
        return
    
    w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={'timeout': 10}))
    
    if not w3.is_connected():
        print(f"  [ERROR] Cannot connect to RPC: {rpc[:40]}...")
        return
    
    block = w3.eth.block_number
    print(f"\n[BLOCK] {chain.upper()} - Block #{block}")
    print(f"  RPC: {rpc[:50]}...")
    
    weth_key = "WETH" if chain == "ethereum" else "WMATIC"
    weth_addr = TOKEN_ADDRESSES[chain].get(weth_key)
    router = w3.to_checksum_address(router_address)
    
    print(f"\n  DEX: {dex_name} @ {router_address[:42]}")
    print(f"  Base: {weth_key} @ {weth_addr[:42]}")
    print(f"\n  Token Prices (1 {weth_key} = ? tokens):")
    
    for token_name, token_addr in tokens.items():
        if token_name == weth_key:
            continue
        token_addr = w3.to_checksum_address(token_addr)
        price = get_price(w3, router, weth_addr, token_addr)
        if price:
            print(f"    {token_name:6s}: {price:.4f}")
        else:
            print(f"    {token_name:6s}: [ERROR] Failed")

def check_uniswap_pairs(chain):
    """Check all Uniswap V2 pairs for price differences"""
    from web3 import Web3
    
    rpc = get_rpc(chain)
    if not rpc:
        return
    
    w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={'timeout': 10}))
    if not w3.is_connected():
        print(f"  [ERROR] Cannot connect to RPC")
        return
    
    # Uniswap V2 Factory
    factory_addr = "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f"
    
    # Try to get pair count (this is slow, so we'll just sample)
    print(f"\n  [SEARCH] Scanning for arbitrage opportunities...")
    
    # Test specific pairs
    tokens = TOKEN_ADDRESSES.get(chain, {})
    weth_key = "WETH" if chain == "ethereum" else "WMATIC"
    weth_addr = tokens.get(weth_key)
    
    if not weth_addr:
        return
    
    # Get prices on different DEXs
    dexes = {
        "Uniswap V2": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
        "Sushiswap": "0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F"
    }
    
    prices = {}
    for dex_name, router_addr in dexes.items():
        prices[dex_name] = {}
        for token_name, token_addr in tokens.items():
            if token_name == weth_key:
                continue
            price = get_price(w3, router_addr, weth_addr, token_addr)
            if price:
                prices[dex_name][token_name] = price
    
    # Compare prices
    print(f"\n  Price Comparison (1 {weth_key} = X tokens):")
    print(f"  {'Token':<10} {'Uniswap':<12} {'Sushiswap':<12} {'Diff %':<10}")
    print(f"  {'-'*44}")
    
    for token_name in prices["Uniswap"]:
        u_price = prices["Uniswap"].get(token_name, 0)
        s_price = prices["Sushiswap"].get(token_name, 0)
        
        if u_price and s_price and u_price > 0:
            diff_pct = abs(u_price - s_price) / ((u_price + s_price) / 2) * 100
            indicator = "[OK]" if diff_pct > 1 else ""
            print(f"  {token_name:<10} {u_price:<12.4f} {s_price:<12.4f} {diff_pct:>6.2f}% {indicator}")
            
            if diff_pct > 1:
                print(f"    [ALERT] POTENTIAL ARBITRAGE: {diff_pct:.2f}% spread!")
    
    return prices

def main():
    print("=" * 70)
    print("[SCANNER] LIVE BLOCKCHAIN PRICE SCANNER")
    print("=" * 70)
    
    # Check Ethereum
    print("\n" + "=" * 50)
    print("[ETH] ETHEREUM MAINNET")
    print("=" * 50)
    
    chain = "ethereum"
    router = get_router(chain)
    tokens = {k: v for k, v in TOKEN_ADDRESSES[chain].items() if k != "WETH"}
    check_dex_price_diff(chain, "Uniswap V2", router, tokens)
    
    check_uniswap_pairs(chain)
    
    # Check Polygon
    print("\n" + "=" * 50)
    print("[POLY] POLYGON MAINNET")
    print("=" * 50)
    
    chain = "polygon"
    router = get_router(chain)
    tokens = {k: v for k, v in TOKEN_ADDRESSES[chain].items() if k != "WMATIC"}
    check_dex_price_diff(chain, "Quickswap", router, tokens)
    
    print("\n" + "=" * 70)
    print("SCAN COMPLETE")
    print("=" * 70)
    print("""
WHY NO ARBITRAGE OPPORTUNITIES?

1. MARKET EFFICIENCY: Modern DEXs use sophisticated pricing (AMM + oracle feeds)
   - Prices are synced across DEXs within seconds
   - Profitable gaps are typically <0.5%

2. GAS COSTS: Ethereum gas is expensive ($20-50+ per swap)
   - Even 1-2% price differences may not cover gas
   - Multi-hop arbitrage requires 2-3 swaps = $60-150 in gas

3. COMPETITION: MEV bots front-run all large opportunities
   - Jito, Beaver, etc. capture ~90% of arb profits
   - Your opportunities need to be >2-3% to be worth it

4. RPC LATENCY: Alchemy/Infura have ~200-500ms delay
   - Real opportunities flash in/out in <1 second
   - Need dedicated infrastructure to compete

5. MIN_PROFIT THRESHOLD: Bot requires $50+ profit
   - Most opportunities are smaller
   - You can lower MIN_USD_PROFIT in bot.py line 141
""")

if __name__ == "__main__":
    main()