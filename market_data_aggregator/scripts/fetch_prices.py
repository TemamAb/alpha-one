import json
import os
from web3 import Web3

# Minimal ABI for Uniswap V2 Router (getAmountsOut) and ERC20 (decimals)
ROUTER_ABI = [
    {"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"}],"name":"getAmountsOut","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"view","type":"function"}
]
ERC20_ABI = [
    {"constant":True,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"payable":False,"stateMutability":"view","type":"function"}
]

def _load_config():
    """
    Loads the contracts.json config file.
    Attempts to locate it relative to this script or in the current working directory.
    """
    # Path resolution: flashloan_app/market_data_aggregator/scripts -> flashloan_app/config_asset_registry/data/
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # flashloan_app/market_data_aggregator
    config_path = os.path.join(base_path, "..", "..", "config_asset_registry", "data", "contracts.json")
    
    if not os.path.exists(config_path):
        # Fallback for execution from project root
        if os.path.exists("config_asset_registry/data/contracts.json"):
            config_path = "config_asset_registry/data/contracts.json"
        else:
            raise FileNotFoundError(f"Configuration file not found at {config_path}")
            
    with open(config_path) as f:
        return json.load(f)

def fetch_prices(chain, token):
    """
    Fetches the price of a token in terms of the chain's native wrapped token (e.g., WETH, WBNB).
    Returns the price as a float.
    """
    try:
        config = _load_config()
        if chain not in config:
            print(f"Chain '{chain}' not found in configuration.")
            return 0.0

        chain_data = config[chain]
        rpc_url = chain_data.get('rpc')
        # Assuming 'router_dex' key exists for the DEX router address
        router_address = chain_data.get('router_dex') 
        # Assuming 'weth_address' key exists for the base asset (WETH/WBNB/etc)
        base_token = chain_data.get('weth_address')

        if not rpc_url or not router_address or not base_token:
            print(f"Incomplete configuration for chain '{chain}'.")
            return 0.0

        w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not w3.is_connected():
            print(f"Failed to connect to RPC: {rpc_url}")
            return 0.0

        token = w3.to_checksum_address(token)
        base_token = w3.to_checksum_address(base_token)
        
        if token == base_token:
            return 1.0

        # Get token decimals
        token_contract = w3.eth.contract(address=token, abi=ERC20_ABI)
        try:
            decimals = token_contract.functions.decimals().call()
        except Exception:
            decimals = 18 # Fallback to 18

        router_contract = w3.eth.contract(address=router_address, abi=ROUTER_ABI)
        amount_in = 10 ** decimals
        
        # amounts[0] is input amount, amounts[1] is output amount in base_token
        amounts = router_contract.functions.getAmountsOut(amount_in, [token, base_token]).call()
        
        # Normalize price (assuming base token has 18 decimals)
        price = amounts[1] / 10**18
        return price

    except Exception as e:
        print(f"Error fetching price for {token} on {chain}: {e}")
        return 0.0
