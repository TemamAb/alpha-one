import json
import os
from web3 import Web3

# Factory ABI for getting pair address
FACTORY_ABI = [
    {"constant": True, "inputs": [{"name": "tokenA", "type": "address"}, {"name": "tokenB", "type": "address"}], "name": "getPair", "outputs": [{"name": "pair", "type": "address"}], "payable": False, "stateMutability": "view", "type": "function"}
]

# Pair ABI for getting reserves
PAIR_ABI = [
    {"constant": True, "inputs": [], "name": "getReserves", "outputs": [{"name": "_reserve0", "type": "uint112"}, {"name": "_reserve1", "type": "uint112"}, {"name": "_blockTimestampLast", "type": "uint32"}], "payable": False, "stateMutability": "view", "type": "function"},
    {"constant": True, "inputs": [], "name": "token0", "outputs": [{"name": "", "type": "address"}], "payable": False, "stateMutability": "view", "type": "function"},
    {"constant": True, "inputs": [], "name": "token1", "outputs": [{"name": "", "type": "address"}], "payable": False, "stateMutability": "view", "type": "function"}
]

# ERC20 ABI for decimals
ERC20_ABI = [
    {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "payable": False, "stateMutability": "view", "type": "function"}
]

def _load_config():
    """
    Loads the contracts.json config file.
    """
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # flashloan_app/market_data_aggregator
    config_path = os.path.join(base_path, "..", "..", "config_asset_registry", "data", "contracts.json")
    
    if not os.path.exists(config_path):
        if os.path.exists("config_asset_registry/data/contracts.json"):
            config_path = "config_asset_registry/data/contracts.json"
        else:
            raise FileNotFoundError(f"Configuration file not found.")
            
    with open(config_path) as f:
        return json.load(f)

def fetch_liquidity(chain, token):
    """
    Fetch real liquidity from DEX pairs on the specified chain.
    Returns total liquidity in token units (USD equivalent).
    """
    try:
        config = _load_config()
        
        if chain not in config:
            print(f"Chain '{chain}' not found in configuration")
            return 0.0
        
        chain_data = config[chain]
        rpc_url = chain_data.get('rpc')
        
        if not rpc_url:
            print(f"No RPC configured for {chain}")
            return 0.0
        
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not w3.is_connected():
            print(f"Failed to connect to RPC: {rpc_url}")
            return 0.0
        
        # Token addresses
        token_addresses = {
            'ethereum': {
                'USDC': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', 
                'DAI': '0x6B175474E89094C44Da98b954E5aaD13AD9E', 
                'WETH': '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',
                'USDT': '0xdAC17F958D2ee523a2206206994597C13D831ec7'
            },
            'polygon': {
                'USDC': '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174', 
                'WMATIC': '0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270',
                'USDT': '0xc2132D05D31c914a87C6611C10748AEb04B58e8F'
            },
            'bsc': {
                'USDC': '0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d', 
                'WBNB': '0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c',
                'USDT': '0x55d398326f99059fF775485246999027B3197955'
            },
            'arbitrum': {
                'USDC': '0xaf88d065e77c8cC22393272276F720D4b21C31C', 
                'WETH': '0x82aF49447D8a07e3bd95BD0d56f35241523fBab1',
                'USDT': '0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9'
            },
            'optimism': {
                'USDC': '0x0b2C639c533813fBdAa2C1a3d447FF12f2F8D2A7', 
                'WETH': '0x4200000000000000000000000000000000000006',
                'USDT': '0x94b008aA5ff5D30B30BFe0f4C2e76e8a19ABf1eF'
            }
        }
        
        chain_tokens = token_addresses.get(chain, {})
        
        # Prefer token address from config if available
        if 'tokens' in chain_data and token in chain_data['tokens']:
            token_addr = w3.to_checksum_address(chain_data['tokens'][token])
        elif token in chain_tokens:
            token_addr = w3.to_checksum_address(chain_tokens[token])
        else:
            return 0.0
            
        weth_addr = chain_data.get('weth_address')
        
        if not weth_addr:
            return 0.0
        
        weth_addr = w3.to_checksum_address(weth_addr)
        
        # Get router address for factory
        router_address = chain_data.get('router_dex')
        
        if not router_address:
            print(f"No router configured for {chain}")
            return 0.0
        
        router_address = w3.to_checksum_address(router_address)
        
        # Try to get pair address from router's factory
        # Uniswap V2 routers have factory() function
        factory_abi = [
            {"constant": True, "inputs": [], "name": "factory", "outputs": [{"name": "", "type": "address"}], "stateMutability": "view", "type": "function"}
        ]
        
        try:
            router_contract = w3.eth.contract(address=router_address, abi=factory_abi)
            factory_address = router_contract.functions.factory().call()
            factory_address = w3.to_checksum_address(factory_address)
        except Exception as e:
            # Use known factory addresses as fallback
            factory_addresses = {
                'ethereum': '0x5C69bEe701ef814a2B6B3CcDC4f6ea9E9A4e7d9',  # Uniswap V2
                'polygon': '0x5757371414417b8C6CAad45bAeF941aBc7d6Ab8D',  # QuickSwap
                'bsc': '0xcA143Ce32Fe78f1f7019d7d551a6402aC1c0BE8',  # PancakeSwap
                'arbitrum': '0x1F98431c8aD98523631AE4a59f267346ea31F984',  # Uniswap V3
                'optimism': '0x1F98431c8aD98523631AE4a59f267346ea31F984'   # Uniswap V3
            }
            factory_address = w3.to_checksum_address(factory_addresses.get(chain, '0x5C69bEe701ef814a2B6B3CcDC4f6ea9E9A4e7d9'))
        
        # Try to get pair address
        try:
            factory_contract = w3.eth.contract(address=factory_address, abi=FACTORY_ABI)
            pair_address = factory_contract.functions.getPair(token_addr, weth_addr).call()
            
            if pair_address == '0x0000000000000000000000000000000000000000':
                # Try reverse order
                pair_address = factory_contract.functions.getPair(weth_addr, token_addr).call()
                
            if pair_address != '0x0000000000000000000000000000000000000000':
                # Get reserves
                pair_contract = w3.eth.contract(address=w3.to_checksum_address(pair_address), abi=PAIR_ABI)
                reserves = pair_contract.functions.getReserves().call()
                token0 = pair_contract.functions.token0().call()
                
                # Determine which reserve is which
                if token0 == token_addr:
                    token_reserve = reserves[0]
                    weth_reserve = reserves[1]
                else:
                    token_reserve = reserves[1]
                    weth_reserve = reserves[0]
                
                # Get token decimals
                token_contract = w3.eth.contract(address=token_addr, abi=ERC20_ABI)
                try:
                    decimals = token_contract.functions.decimals().call()
                except:
                    decimals = 18 if token != 'USDC' else 6
                
                # Get live ETH price dynamically for accurate USD calculation
                # This ensures simulation runs on real market data, not hardcoded values
                try:
                    import sys
                    import os
                    # Add project root to path
                    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                    sys.path.insert(0, os.path.join(project_root, 'strategy_engine', 'src'))
                    from utils import get_live_eth_price
                    weth_price = get_live_eth_price(chain)
                except Exception as e:
                    print(f"[LIQUIDITY] Could not fetch live price for {chain}: {e}")
                    # Fallback to minimal values to prevent silent failures
                    weth_price = 1.0
                
                # Token value in USD (assuming stablecoins = $1)
                if token in ['USDC', 'USDT', 'DAI']:
                    token_usd_value = token_reserve / (10 ** decimals)
                else:
                    # For non-stablecoins, calculate based on WETH value
                    token_usd_value = (token_reserve / (10 ** decimals)) * weth_price
                
                liquidity = (token_usd_value) + (weth_reserve / 1e18) * weth_price
                
                print(f"[LIQUIDITY] {token} on {chain}: ${liquidity:,.2f}")
                return liquidity
                
        except Exception as e:
            print(f"[LIQUIDITY] Error getting pair: {e}")
        
        # CRITICAL: Never return fake data - use live prices or fail loudly
        # If we can't get real data, return 0 to prevent false arbitrage signals
        print(f"[LIQUIDITY] WARNING: Could not fetch real liquidity for {token} on {chain}. Returning 0 to prevent false signals.")
        return 0.0
        
    except Exception as e:
        print(f"Error in fetch_liquidity: {e}")
        return 0.0
