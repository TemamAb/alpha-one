from web3 import Web3
import json
import os
import time
import requests

# Fixed config load - relative to flashloan_app (like test_rpc.py)
config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), 'flashloan_app', 'config_asset_registry', 'data', 'contracts.json')

print(f"[UTILS] Config path: {config_path}")

try:
    with open(config_path) as f:
        CONFIG = json.load(f)
    print(f"[UTILS] Config loaded! Keys: {list(CONFIG.keys())}")
except Exception as e:
    print(f"ERROR: Could not load config from {config_path}: {e}")
    CONFIG = {}

# Uniswap V2 Router ABI
ROUTER_ABI = [
    {"inputs": [{"internalType": "uint256", "name": "amountIn", "type": "uint256"}, {"internalType": "address[]", "name": "path", "type": "address[]"}], "name": "getAmountsOut", "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}], "stateMutability": "view", "type": "function"}
]

ERC20_ABI = [
    {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "payable": False, "stateMutability": "view", "type": "function"}
]

# Token addresses (hardcoded fallback)
TOKEN_ADDRESSES = {
    'ethereum': {'USDC': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', 'DAI': '0x6B175474E89094C44Da98b954E5aaD13AD9E9', 'WETH': '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2', 'USDT': '0xdAC17F958D2ee523a2206206994597C13D831ec7', 'WBTC': '0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599', 'LINK': '0x514910771AF9Ca656af840dff83E8264EcF986CA', 'UNI': '0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984'},
    'polygon': {'USDC': '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174', 'WMATIC': '0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270', 'USDT': '0xc2132D05D31c914a87C6611C10748AEb04B58e8F'},
    'bsc': {'USDC': '0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d', 'WBNB': '0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c', 'USDT': '0x55d398326f99059fF775485246999027B3197955'},
    'arbitrum': {'USDC': '0xaf88d065e77c8cC22393272276F720D4b21C31C', 'WETH': '0x82aF49447D8a07e3bd95BD0d56f35241523fBab1'},
    'optimism': {'USDC': '0x0b2C639c533813fBdAa2C1a3d447FF12f2F8D2A7', 'WETH': '0x4200000000000000000000000000000000000006'}
}

# Gas prices (GWEI to USD, approx ETH=$3000)
GAS_PRICES = {
    'ethereum': {'fast': 30, 'avg': 20},  # ~$30-50 per tx
    'polygon': {'fast': 100, 'avg': 50},   # ~$0.10
    'bsc': {'fast': 5, 'avg': 3},
    'arbitrum': {'fast': 1, 'avg': 0.5},
    'optimism': {'fast': 1, 'avg': 0.5}
}

ETH_USD = 3000  # Update dynamically in production

# --- Enterprise Upgrade: Persistent Connection Pool ---
_W3_CACHE = {}

def get_w3_session():
    """Creates a requests Session with TCP Keep-Alive for low latency"""
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def get_rpc(chain):
    # Check cache first for instant access
    if chain in _W3_CACHE:
        return _W3_CACHE[chain]['rpc']

    if chain in CONFIG:
        rpcs = []
        main = CONFIG[chain].get('rpc')
        fb = CONFIG[chain].get('rpc_fallback')
        if main:
            rpcs.append(main)
        if fb:
            rpcs.append(fb)
        for rpc in rpcs:
            try:
                # Use persistent session provider
                provider = Web3.HTTPProvider(rpc, session=get_w3_session(), request_kwargs={'timeout': 5})
                w3 = Web3(provider)
                if w3.is_connected():
                    # Cache the successful W3 instance
                    _W3_CACHE[chain] = {'w3': w3, 'rpc': rpc}
                    return rpc
            except:
                continue
        return rpcs[0] if rpcs else None
    return None

def get_rpc_with_fallback(chain):
    rpcs = []
    if chain in CONFIG:
        if CONFIG[chain].get('rpc'):
            rpcs.append(CONFIG[chain]['rpc'])
        if CONFIG[chain].get('rpc_fallback'):
            rpcs.append(CONFIG[chain]['rpc_fallback'])
        if CONFIG[chain].get('rpc_alt1'):
            rpcs.append(CONFIG[chain]['rpc_alt1'])
        if CONFIG[chain].get('rpc_alt2'):
            rpcs.append(CONFIG[chain]['rpc_alt2'])
    return rpcs or []

def get_router(chain):
    if chain in CONFIG:
        return CONFIG[chain].get('router_dex')
    return None

def get_weth(chain):
    if chain in CONFIG:
        return CONFIG[chain].get('weth_address')
    return None

def get_price(chain, dex_name, token):
    rpcs = get_rpc_with_fallback(chain)
    
    # Use cached w3 if available to skip connection setup
    if chain in _W3_CACHE:
        w3 = _W3_CACHE[chain]['w3']
        rpcs = [_W3_CACHE[chain]['rpc']] # Prioritize cached working RPC
    
    for rpc in rpcs:
        try:
            if chain not in _W3_CACHE: w3 = Web3(Web3.HTTPProvider(rpc, session=get_w3_session(), request_kwargs={'timeout': 5}))
            if w3.eth.block_number is None:
                continue
                
            router = get_router(chain)
            weth = get_weth(chain)
            
            if not router or not weth:
                continue
            
            token_addr = TOKEN_ADDRESSES.get(chain, {}).get(token)
            if not token_addr:
                continue
            
            token_addr = w3.to_checksum_address(token_addr.lower())
            router = w3.to_checksum_address(router.lower())
            weth = w3.to_checksum_address(weth.lower())
            
            if token in ['WETH', 'WMATIC', 'WBNB']:
                return 1.0
            
            decimals = 6 if 'USDC' in token or 'USDT' in token else 18
            
            paths = [[token_addr, weth]]
            
            router_contract = w3.eth.contract(address=router, abi=ROUTER_ABI)
            
            for path in paths:
                try:
                    amount_in = 10 ** decimals
                    amounts = router_contract.functions.getAmountsOut(amount_in, path).call()
                    price = amounts[-1] / 10**18
                    return price
                except:
                    continue
            
        except:
            continue
    
    return 0.0

def get_multiple_prices(chain, dex_name, tokens):
    """Batch price fetching for speed"""
    prices = {}
    for token in tokens:
        prices[token] = get_price(chain, dex_name, token)
    return prices

def estimate_gas_cost(chain):
    """Estimate flashloan arb tx gas cost in USD"""
    if chain not in GAS_PRICES:
        return 20.0
    gas_price_gwei = GAS_PRICES[chain]['fast']
    gas_used = 800000  # Flashloan + 2 swaps
    eth_price = ETH_USD / 1e9  # gwei to eth
    return gas_price_gwei * gas_used * eth_price

def calculate_profit(buy_price, sell_price):
    return sell_price - buy_price

def estimate_net_profit(gross_profit_tokens, buy_price, chain, dex_fee_pct=0.003):
    """
    gross_profit_tokens: profit in base token
    buy_price: base token USD price
    """
    gross_usd = gross_profit_tokens * buy_price
    dex_fees = gross_usd * dex_fee_pct * 2  # buy + sell
    gas_usd = estimate_gas_cost(chain)
    relayer_fee = gross_usd * 0.001  # 0.1%
    net_usd = gross_usd - dex_fees - gas_usd - relayer_fee
    return net_usd

def get_top_pairs():
    """Load volatile pairs config"""
    try:
        with open('volatile_pairs.json') as f:
            data = json.load(f)
        return data['top_pairs']
    except:
        # Fallback
        return [{"base": "WETH", "quote": "USDC"}]

def estimate_optimal_trade_size(net_profit_target_usd, buy_price, chain, max_slippage=0.005):
    """
    Calculate optimal input size for target profit at max slippage
    """
    gas_cost = estimate_gas_cost(chain)
    target_gross_usd = net_profit_target_usd + gas_cost
    optimal_size_tokens = target_gross_usd / buy_price
    return optimal_size_tokens

def estimate_relayer_fee(chain, token):
    return 0.00001
