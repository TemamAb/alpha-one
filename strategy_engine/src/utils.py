from web3 import Web3
import itertools
import json
import os
import logging
import requests
import time
import redis

try:
    from . import multicall
    from . import price_provider
except (ImportError, ValueError):
    import multicall
    import price_provider

logger = logging.getLogger(__name__)

# --- Path Configuration ---
# Simplified and robust path logic
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
config_path = os.path.join(PROJECT_ROOT, 'config_asset_registry', 'data', 'contracts.json')


def get_live_eth_price(chain=None):
    """
    Fetches live native token price through the dedicated provider layer.
    """
    if chain and 'local' in chain.lower():
        chain = 'ethereum' if 'eth' in chain.lower() else ('polygon' if 'poly' in chain.lower() else 'bsc')
    return price_provider.get_chain_price(chain or 'ethereum')

# Gas prices in Gwei for different chains
# TODO: Replace with a live gas oracle feed (e.g., eth_gasStation) in production.
GAS_PRICES = {
    'ethereum': {'fast': 20, 'standard': 15, 'slow': 10},
    'polygon': {'fast': 50, 'standard': 40, 'slow': 30},
    'bsc': {'fast': 5, 'standard': 3, 'slow': 2},
    'arbitrum': {'fast': 0.1, 'standard': 0.08, 'slow': 0.05},
    'optimism': {'fast': 0.001, 'standard': 0.0008, 'slow': 0.0005},
    'base': {'fast': 0.001, 'standard': 0.0008, 'slow': 0.0005},
    'avalanche': {'fast': 30, 'standard': 25, 'slow': 20},
    'localethereum': {'fast': 20, 'standard': 15, 'slow': 10},
    'localpolygon': {'fast': 50, 'standard': 40, 'slow': 30},
    'localbsc': {'fast': 5, 'standard': 3, 'slow': 2}
}

def get_live_gas_prices(chain):
    """
    Fetches live gas prices from the chain RPC.
    """
    try:
        rpc = get_rpc(chain) # Initializes W3 cache if needed
        if chain in _W3_CACHE:
            w3 = _W3_CACHE[chain]['w3']
            if w3.is_connected():
                gas_price = w3.eth.gas_price # Wei
                gas_gwei = float(w3.from_wei(gas_price, 'gwei'))
                live_prices = {
                    'fast': gas_gwei * 1.25,
                    'standard': gas_gwei,
                    'slow': gas_gwei * 0.8
                }
                # Architect Fix: Detection of "Dust Gas" (likely misconfigured local node)
                # Ethereum production gas is virtually never < 0.5 Gwei. 
                if chain == 'ethereum' and gas_gwei < 0.1:
                    raise ValueError("Suspiciously low gas price detected from RPC")
                return live_prices
    except Exception as e:
        logger.warning(f"Failed to fetch live gas for {chain}: {e}")

    # Fallback to hardcoded
    if chain not in GAS_PRICES:
        logger.warning(f"No hardcoded gas prices for {chain}, using 'ethereum' defaults.")

    gas_prices_for_chain = GAS_PRICES.get(chain, GAS_PRICES['ethereum'])
    logger.warning(f"Using hardcoded gas prices for {chain} (Fallback).")
    return gas_prices_for_chain

print(f"[UTILS] Config path: {config_path}")

try:
    with open(config_path) as f:
        CONFIG = json.load(f)
    print(f"[UTILS] Config loaded! Keys: {list(CONFIG.keys())}")
    SUPPORTED_CHAINS = list(CONFIG.keys())
except (FileNotFoundError, json.JSONDecodeError) as e:
    print(f"ERROR: Could not load config from {config_path}: {e}")
    CONFIG = {}

# Uniswap V2 Router ABI
ROUTER_ABI = [
    {"inputs": [{"internalType": "uint256", "name": "amountIn", "type": "uint256"}, {"internalType": "address[]", "name": "path", "type": "address[]"}], "name": "getAmountsOut", "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}], "stateMutability": "view", "type": "function"}
]

ERC20_ABI = [
    {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "payable": False, "stateMutability": "view", "type": "function"}
]

# --- ABIs for Dynamic Graph Building (KPI #2) ---
FACTORY_ABI = [{"constant":True,"inputs":[{"internalType":"uint256","name":"","type":"uint256"}],"name":"allPairs","outputs":[{"internalType":"address","name":"","type":"address"}],"payable":False,"stateMutability":"view","type":"function"}, {"constant":True,"inputs":[],"name":"allPairsLength","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"payable":False,"stateMutability":"view","type":"function"}]
PAIR_ABI = [{"constant":True,"inputs":[],"name":"token0","outputs":[{"internalType":"address","name":"","type":"address"}],"payable":False,"stateMutability":"view","type":"function"}, {"constant":True,"inputs":[],"name":"token1","outputs":[{"internalType":"address","name":"","type":"address"}],"payable":False,"stateMutability":"view","type":"function"}]


# Token addresses (hardcoded fallback)
TOKEN_ADDRESSES = {
    'ethereum': {
        'USDC': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',
        'USDT': '0xdAC17F958D2ee523a2206206994597C13D831ec7',
        'WETH': '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',
        'DAI': '0x6B175474E89094C44Da98b954EedeAC495271d0F',
        'WBTC': '0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599',
        'LINK': '0x514910771AF9Ca656af840dff83E8264EcF986CA',
        'UNI': '0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984',
        'AAVE': '0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9',
        'CRV': '0xD533a949740bb3306d119CC777fa900bA034cd52',
        'COMP': '0xc00e94Cb662C3520282E6f5717214004A7f26888',
        'MKR': '0x9f8F72aA9304c8B593d555F12eF6589cC3A579A2',
        'SNX': '0xC011A72400E58ecD99Ee497CF89E3775d4bd732F',
        'LDO': '0x5A98FcBEA516Cf06857215779Fd812CA3beF1B32',
        'RPL': '0xD33526068D116cE69F19A9ee46F0bd304F21A51f',
        'BAL': '0xba100000625a3754423978a60c9317c58a424e3D'
    },
    'polygon': {'USDC': '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174', 'WMATIC': '0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270', 'USDT': '0xc2132D05D31c914a87C6611C10748AEb04B58e8F'},
    'bsc': {'USDC': '0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d', 'WBNB': '0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c', 'USDT': '0x55d398326f99059fF775485246999027B3197955'},
    'arbitrum': {'USDC': '0xaf88d065e77c8cC2239327C5EDb3A432268e5831', 'WETH': '0x82aF49447D8a07e3bd95BD0d56f35241523fBab1'},
    'optimism': {'USDC': '0x0b2C639c533813fBdAa2C1a3d447FF12f2F8D2A7', 'WETH': '0x4200000000000000000000000000000000000006'}
}

# --- Enterprise Upgrade: Persistent Connection Pool ---
_PAIR_CACHE = {}
_W3_CACHE = {}
_BAD_FACTORY_CACHE = set()
_RPC_LATENCY_CACHE = {}
_REDIS_CLIENT = None

def _dedupe_preserve_order(values):
    seen = set()
    deduped = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped

def _record_rpc_latency(chain, latency_ms):
    if not chain:
        return
    previous = _RPC_LATENCY_CACHE.get(chain, 0.0)
    smoothed_latency = latency_ms if previous == 0 else ((previous * 0.7) + (latency_ms * 0.3))
    _RPC_LATENCY_CACHE[chain] = smoothed_latency
    redis_client = _get_redis_client()
    if redis_client:
        try:
            redis_client.hset("alphamark:rpc_latency", chain, round(smoothed_latency, 2))
            redis_client.expire("alphamark:rpc_latency", 300)
        except Exception:
            pass

def _get_redis_client():
    global _REDIS_CLIENT
    if _REDIS_CLIENT is not None:
        return _REDIS_CLIENT

    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        return None

    try:
        _REDIS_CLIENT = redis.from_url(redis_url, socket_timeout=1, socket_connect_timeout=1)
        _REDIS_CLIENT.ping()
    except Exception:
        _REDIS_CLIENT = None
    return _REDIS_CLIENT

def get_rpc_latency_snapshot():
    redis_client = _get_redis_client()
    if redis_client:
        try:
            raw_snapshot = redis_client.hgetall("alphamark:rpc_latency")
            if raw_snapshot:
                snapshot = {}
                for chain, latency in raw_snapshot.items():
                    chain_name = chain.decode() if isinstance(chain, bytes) else str(chain)
                    try:
                        snapshot[chain_name] = round(float(latency), 2)
                    except (TypeError, ValueError):
                        continue
                if snapshot:
                    return snapshot
        except Exception:
            pass
    return {chain: round(latency, 2) for chain, latency in _RPC_LATENCY_CACHE.items()}

def get_preferred_rpcs(chain):
    rpcs = []
    if chain in CONFIG:
        for key in ['rpc_production', 'rpc_alt1', 'rpc_alt2', 'rpc_fallback', 'rpc']:
            rpc = CONFIG[chain].get(key)
            if rpc and 'YOUR' not in rpc and 'YOUR_' not in rpc:
                rpcs.append(rpc)

    env_var_candidates = [f"{chain.upper()}_RPC_URL", f"{chain.upper()}_RPC"]
    if chain == "ethereum":
        env_var_candidates = ["ETH_RPC_URL", "ETHEREUM_RPC_URL", "ETH_RPC", "ETHEREUM_RPC"] + env_var_candidates

    # CHECK REDIS FIRST for dynamic runtime overrides
    redis_client = _get_redis_client()
    for var in env_var_candidates:
        # Check Redis Hash
        if redis_client:
            try:
                val = redis_client.hget("alphamark:env", var)
                if val:
                    val_str = val.decode() if isinstance(val, bytes) else str(val)
                    if val_str: rpcs.insert(0, val_str)
            except Exception: pass
            
        # Fallback to local process environment
        val = os.environ.get(var)
        if val:
            rpcs.insert(0, val)

    rpcs = _dedupe_preserve_order(rpcs)

    # Execution/bundler endpoints are valid for user operations but poor choices for heavy market-data scans.
    execution_style_endpoints = [
        rpc for rpc in rpcs
        if any(pattern in rpc.lower() for pattern in ["api.pimlico.io", "/v1/", "/v2/"])
    ]
    data_rpcs = [rpc for rpc in rpcs if rpc not in execution_style_endpoints]

    # De-prioritize public fallback endpoints that are frequently rate-limited if better RPCs exist.
    noisy_public_endpoints = {
        'ethereum': {'https://eth.llamarpc.com', 'https://eth.llamarpc.com/'},
        'arbitrum': {'https://arb1.arbitrum.io/rpc'},
        'base': {'https://mainnet.base.org'},
        'optimism': {'https://mainnet.optimism.io'}
    }
    noisy = noisy_public_endpoints.get(chain, set())
    preferred = [rpc for rpc in data_rpcs if rpc not in noisy]
    deferred_public = [rpc for rpc in data_rpcs if rpc in noisy]
    return preferred + deferred_public + execution_style_endpoints

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
    
    # Collect potential RPCs for validation
    candidate_rpcs = get_preferred_rpcs(chain)

    for rpc in candidate_rpcs:
        if not rpc or "YOUR_KEY" in rpc or "YOUR_PROJECT_ID" in rpc:
            continue
        # Architect Fix: Filter out local RPCs in Paper/Live mode
        is_local = "127.0.0.1" in rpc or "localhost" in rpc
        if is_local and os.environ.get("PAPER_TRADING_MODE") == "true":
            continue

        try:
            started = time.time()
            provider = Web3.HTTPProvider(rpc, session=get_w3_session(), request_kwargs={'timeout': 3})
            w3 = Web3(provider)
            if w3.eth.block_number > 0:
                _record_rpc_latency(chain, (time.time() - started) * 1000)
                _W3_CACHE[chain] = {'w3': w3, 'rpc': rpc}
                return rpc
        except Exception:
            continue
    
    # Architect Fix: Return None only if no RPCs worked, ensuring caller handles failure
    return _W3_CACHE[chain]['rpc'] if chain in _W3_CACHE else None

def get_rpc_with_fallback(chain):
    return get_preferred_rpcs(chain)

def get_router(chain):
    if chain in CONFIG:
        return CONFIG[chain].get('router_dex')
    return None

def get_weth(chain):
    if chain in CONFIG:
        return CONFIG[chain].get('weth_address')
    return None

def get_price(chain, dex_name, token):
    """
    Get the price of a token on a specific DEX.
    Now uses a cached web3 instance and prioritizes it.
    """
    if chain not in SUPPORTED_CHAINS:
        raise ValueError(f"Chain {chain} not supported.")
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
            
            # Prefer token address from config if available, fallback to hardcoded
            token_addr = None
            if chain in CONFIG and 'tokens' in CONFIG[chain]:
                token_addr = CONFIG[chain]['tokens'].get(token)
            if not token_addr:
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

def get_all_dex_pairs(w3, factory_address, chain_name=None):
    """
    Enhanced: Fetches all pair addresses with RPC rotation, rate limiting & retry.
    """
    factory_address = w3.to_checksum_address(factory_address)
    if factory_address in _BAD_FACTORY_CACHE:
        logger.warning(f"[GRAPH] Skipping known-bad factory {factory_address}", extra={"chain": chain_name})
        return {}
    if factory_address in _PAIR_CACHE:
        logger.info(f"[GRAPH] Cache hit for {factory_address}")
        return _PAIR_CACHE[factory_address]

    # Get RPC list for rotation from config
    rpc_list = get_preferred_rpcs(chain_name) if chain_name else []
    if not rpc_list:
        rpc_list = [w3.provider.endpoint_uri]

    factory = w3.eth.contract(address=factory_address, abi=FACTORY_ABI)
    graph = {}
    # Dynamic pair limit based on chain - balance coverage vs latency
    chain_pair_limits = {
        'ethereum': 2000,      # Mainnet - scan more pairs
        'polygon': 1000,       # L2 - balanced
        'bsc': 1500,          # BSC - good coverage
        'arbitrum': 1200,      # L2 - scan more
        'optimism': 1200,      # L2 - scan more
        'base': 1200,          # L2 - scan more
        'avalanche': 1000      # Avalanche - balanced
    }
    
    # --- DYNAMIC OPTIMIZATION: Adaptive Pair Scanning ---
    # Adjust max_pairs based on the latency of the provided w3 instance
    try:
        start_t = time.time()
        w3.eth.block_number
        rpc_latency = (time.time() - start_t) * 1000
        _record_rpc_latency(chain_name, rpc_latency)
    except:
        rpc_latency = 500

    base_limit = chain_pair_limits.get(chain_name, 1000)
    
    # Optimizing scan depth based on RPC health
    if rpc_latency < 60: 
        optimized_limit = base_limit * 1.5
    elif rpc_latency > 400:
        optimized_limit = base_limit * 0.5
    else:
        optimized_limit = base_limit
        
    max_pairs = int(os.environ.get("MAX_PAIRS_TO_SCAN", str(int(optimized_limit))))
    logger.info(f"Dynamic Pair Optimization: Scanning up to {max_pairs} pairs (RPC Latency: {rpc_latency:.0f}ms)", extra={"chain": chain_name})

    try:
        length = factory.functions.allPairsLength().call()
        if not isinstance(length, int) or length <= 0:
            logger.warning(f"[GRAPH] Factory {factory_address} returned invalid pair length: {length}", extra={"chain": chain_name})
            _BAD_FACTORY_CACHE.add(factory_address)
            return {}
        num_to_fetch = min(length, max_pairs)
        logger.info(f"Fetching {num_to_fetch}/{length} pairs via resilient multicall", extra={"chain": chain_name})

        # Global semaphore for concurrency control
        import threading
        semaphore = threading.Semaphore(10)  # Max 10 concurrent batches

        multicaller = multicall.get_multicaller(w3, chain_name=chain_name)
        pair_addresses = []
        batch_size = [20]  # Mutable batch size for adaptive handling
        max_retries = 3
        
        def resilient_multicall(calls, rpc_idx=0, retry_count=0, multicaller=multicaller):
            with semaphore:
                try:
                    if hasattr(multicaller, 'aggregate'):
                        results = multicaller.aggregate(calls)
                    else:
                        batch_reqs = [{"method": "eth_call", "params": [{"to": target, "data": data}, "latest"]} for target, data in calls]
                        results = multicaller.batch_call(batch_reqs)
                    return results, rpc_idx
                except Exception as e:
                    if '429' in str(e) or 'rate limit' in str(e).lower():
                        sleep_time = (2 ** retry_count) * 0.5 + 0.2  # Exp backoff + base
                        logger.warning(f"Rate limit hit (RPC {rpc_idx}). Backoff {sleep_time:.2f}s, retry {retry_count+1}/{max_retries}")
                        time.sleep(sleep_time)
                        if retry_count < max_retries:
                            # Rotate RPC
                            new_rpc_idx = (rpc_idx + 1) % len(rpc_list)
                            if new_rpc_idx != rpc_idx and rpc_list[new_rpc_idx] != w3.provider.endpoint_uri:
                                logger.info(f"Rotating to RPC: {rpc_list[new_rpc_idx][:50]}...")
                                w3.provider = Web3.HTTPProvider(rpc_list[new_rpc_idx], session=get_w3_session(), request_kwargs={'timeout': 10})
                                new_multicaller = multicall.get_multicaller(w3, chain_name=chain_name)  # Re-init
                                # Reduce batch size on RPC rotation to avoid rate limits
                                batch_size[0] = max(5, batch_size[0] // 2)
                                logger.info(f"Reduced batch size to {batch_size[0]} after RPC rotation")
                                return resilient_multicall(calls, new_rpc_idx, retry_count + 1, new_multicaller)
                        else:
                            # Reduce batch size on final fail
                            batch_size[0] = max(5, batch_size[0] // 2)
                            logger.warning(f"Max retries. Reduced batch_size to {batch_size[0]}")
                            return [], rpc_idx
                    raise e

        # Step 1: Pair addresses
        def parse_multicall_address(result):
            if result is None:
                return None
            if isinstance(result, bytes):
                if len(result) >= 20:
                    return w3.to_checksum_address('0x' + result[-20:].hex())
                return None
            if isinstance(result, str):
                if not result.startswith('0x'):
                    return None
                if len(result) >= 42:
                    return w3.to_checksum_address('0x' + result[-40:])
                return None
            return None

        for i in range(0, num_to_fetch, batch_size[0]):
            count = min(batch_size[0], num_to_fetch - i)
            calls = [(factory_address, factory.encodeABI(fn_name="allPairs", args=[j])) for j in range(i, i + count)]
            results, _ = resilient_multicall(calls)
            for res in results:
                pair_address = parse_multicall_address(res)
                if pair_address:
                    pair_addresses.append(pair_address)
            time.sleep(0.1)  # Minimal delay for speed

        # Step 2: Token0/Token1
        pair_contract = w3.eth.contract(abi=PAIR_ABI)
        for i in range(0, len(pair_addresses), batch_size[0]):
            chunk = pair_addresses[i:i + batch_size[0]]
            calls = []
            for pair_addr in chunk:
                calls.append((pair_addr, pair_contract.encodeABI(fn_name="token0")))
                calls.append((pair_addr, pair_contract.encodeABI(fn_name="token1")))
            results, _ = resilient_multicall(calls)
            if not results: continue

            for j in range(0, len(results), 2):
                if j+1 >= len(results): break
                
                r0, r1 = results[j], results[j+1]
                if r0 is None or r1 is None: continue
                
                try:
                    def parse_addr(data):
                        # Expected data: 32 bytes or 66-character hex string (0x + 64 hex)
                        if isinstance(data, bytes):
                            return w3.to_checksum_address('0x' + data[-20:].hex())
                        elif isinstance(data, str) and data.startswith('0x'):
                            # Address is the last 40 characters of the 32-byte slot
                            return w3.to_checksum_address('0x' + data[-40:])
                        return None

                    t0 = parse_addr(r0)
                    t1 = parse_addr(r1)
                    
                    if t0 and t1:
                        graph.setdefault(t0, []).append(t1)
                        graph.setdefault(t1, []).append(t0)
                except Exception:
                    continue
            time.sleep(0.2)

        if not graph and pair_addresses:
            logger.warning(f"[GRAPH] Factory {factory_address} yielded pair addresses but no token graph", extra={"chain": chain_name})
            _BAD_FACTORY_CACHE.add(factory_address)
            return {}

        _PAIR_CACHE[factory_address] = graph
        logger.info(f"✅ Built resilient graph: {len(graph)} tokens, {len(pair_addresses)} pairs")
        return graph
    except Exception as e:
        logger.error(f"Graph build failed after retries: {e}")
        _BAD_FACTORY_CACHE.add(factory_address)
        return graph

def get_dynamic_profit_threshold(chain, risk_multiplier=2.0, min_floor=5.0):
    """
    Calculates a rational dynamic profit threshold.
    Min Profit = (Gas Cost * Multiplier) + Floor
    """
    # ARCHITECT FIX: Validate chain support to trigger fallback for unknown chains
    supported_gas = chain in GAS_PRICES or (chain and chain.startswith('local'))
    
    try:
        if not supported_gas:
            raise ValueError(f"Unsupported chain for dynamic threshold: {chain}")
            
        gas_cost_usd = estimate_gas_cost(chain)
        dynamic_min = (gas_cost_usd * risk_multiplier) + min_floor
        return max(min_floor, dynamic_min)
    except Exception:
        return 50.0  # Safe fallback if gas estimation fails

def estimate_gas_cost(chain):
    """Estimate flashloan arb tx gas cost in USD"""
    # Use the new function to get gas prices
    gas_prices_for_chain = get_live_gas_prices(chain)
    gas_price_gwei = gas_prices_for_chain['fast']
    gas_used = 800000  # Flashloan + 2 swaps

    # Use the function to get the native token price for the specific chain
    native_price_usd = get_live_eth_price(chain)

    # Calculate cost in USD using the correct native token price
    cost_in_native = (gas_price_gwei * 1e9) * gas_used / 1e18
    cost_in_usd = cost_in_native * native_price_usd
    return cost_in_usd

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
        top_pairs = data.get('top_pairs', [])
        if len(top_pairs) >= 100:
            return top_pairs[:100]
    except Exception:
        top_pairs = []

    ethereum_priority_order = [
        'USDC', 'USDT', 'DAI', 'WETH', 'WBTC',
        'LINK', 'UNI', 'AAVE', 'CRV', 'COMP',
        'MKR', 'SNX', 'LDO', 'RPL', 'BAL'
    ]
    generated_pairs = [
        {"base": base, "quote": quote, "priority": index + 1}
        for index, (base, quote) in enumerate(itertools.combinations(ethereum_priority_order, 2))
    ]
    return generated_pairs[:100]

def estimate_optimal_trade_size(net_profit_target_usd, buy_price, chain, max_slippage=0.005):
    """
    Calculate optimal input size for target profit at max slippage
    """
    gas_cost = estimate_gas_cost(chain)
    target_gross_usd = net_profit_target_usd + gas_cost
    optimal_size_tokens = target_gross_usd / buy_price
    return optimal_size_tokens

def estimate_relayer_fee(chain, token):
    """Dummy relayer fee"""
    return 0.00001
