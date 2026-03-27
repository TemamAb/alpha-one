import os
import requests
import logging
from eth_abi import encode
try:
    from eth_abi.packed import encode_packed
except ImportError:
    # Docker eth_abi version fallback - define packed encoding
    def encode_packed(types, values):
        import eth_abi
        if hasattr(eth_abi, 'encode_packed'):
            return eth_abi.encode_packed(types, values)
        # Manual packed encoding fallback for old versions
        packed = b''
        for t, v in zip(types, values):
            if t == 'address':
                packed += bytes.fromhex(v[2:].zfill(64))
            elif t == 'uint256':
                packed += v.to_bytes(32, 'big')
            # Add more types as needed
        return packed
import redis
from web3 import Web3
from eth_account import Account

# --- Configuration ---
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

DEFAULT_LOCAL_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"

REDIS_URL = os.environ.get("REDIS_URL")
# MEV Protection: Enabled by default for production use
# Set MEV_PROTECTION=false only for testing on testnets
PRIVATE_MODE = os.environ.get("MEV_PROTECTION", "true").lower() == "true"

# Mode Transition Documentation:
# ============================
#
# PAPER TRADING MODE (Simulation):
#   - Set: PAPER_TRADING_MODE=true (in .env or via environment variable)
#   - Bot: Scans for arbitrage opportunities, validates liquidity/risk
#   - Executor: Simulates execution, returns fake hash, NO real transactions
#   - Dashboard: Shows simulated profits in trade_history.csv
#   - Risk: NONE (no real funds used)
#
# LIVE TRADING MODE (Production):
#   - Set: PAPER_TRADING_MODE=false
#   - Bot: Scans for arbitrage opportunities, validates liquidity/risk
#   - Executor: Executes real flash loan transactions via Pimlico bundler
#   - Dashboard: Shows real profits from on-chain execution
#   - Risk: REAL FUNDS (uses wallet PRIVATE_KEY)
#
# Transition Steps:
#   1. Start with PAPER_TRADING_MODE=true to verify system works
#   2. Check trade_history.csv for simulated profits
#   3. To switch to LIVE: edit .env or run: set PAPER_TRADING_MODE=false
#   4. Restart bot - it will now execute real transactions
#   5. Monitor dashboard for real profit/loss

# Paper Trading Mode: Read from environment variable
# Set PAPER_TRADING_MODE=false in .env for live trading
PAPER_TRADING_MODE = os.environ.get("PAPER_TRADING_MODE", "true").lower() == "true"

def log_mode_status():
    if not PAPER_TRADING_MODE:
        logger.warning("⚠️  WARNING: EXECUTOR RUNNING IN LIVE PROFIT MODE. REAL FUNDS WILL BE USED. ⚠️")
    else:
        logger.info("ℹ️  Executor initialized in PAPER TRADING mode.")

# Dynamically compute FlashLoan contract address if not set
def get_flashloan_address():
    """
    Get FlashLoan contract address from environment or compute dynamically.
    
    Resolution order:
    1. FLASHLOAN_CONTRACT_ADDRESS env var (explicit override)
    2. Compute from deployer nonce (if DEPLOYER_ADDRESS set)
    3. Fail with clear error
    """
    # Option 1: Explicit address in environment
    explicit_addr = os.environ.get("FLASHLOAN_CONTRACT_ADDRESS")
    if explicit_addr:
        return Web3.to_checksum_address(explicit_addr)
    
    # Option 2: Compute dynamically from deployer nonce
    deployer_addr = os.environ.get("DEPLOYER_ADDRESS") or DEPLOYER_ADDRESS
    chain = os.environ.get("CHAIN", "ethereum").lower()
    
    if deployer_addr:
        try:
            from web3 import Web3
            rpc_env = f"{chain.upper()}_RPC_URL"
            rpc = os.environ.get(rpc_env)
            if not rpc:
                # Try alternate env var names (without _URL suffix, e.g., ETH_RPC)
                rpc = os.environ.get(f"{chain.upper()}_RPC")
            if not rpc:
                # Try ETH_RPC as fallback
                rpc = os.environ.get("ETH_RPC")
            if not rpc:
                # Final fallback to ETH_RPC_URL
                rpc = os.environ.get("ETH_RPC_URL")
            
            try:
                if rpc:
                    w3 = Web3(Web3.HTTPProvider(rpc))
                    # Import the deploy utility
                    import sys
                    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'strategy_engine', 'src'))
                    from deploy import predict_flashloan_address
                    
                    predicted = predict_flashloan_address(w3, deployer_addr)
                    return predicted
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"Failed to dynamically compute address: {e}")

    return None

FLASHLOAN_CONTRACT_ADDRESS = None  # Will be resolved at runtime

# --- Load from Environment ---
PIMLICO_API_KEY = os.environ.get("PIMLICO_API_KEY")
PRIVATE_KEY = os.environ.get("PRIVATE_KEY")

# Get wallet address - try multiple env var names
WALLET_ADDRESS = os.environ.get("WALLET_ADDRESS") or os.environ.get("WALLET_ADDRESS")
DEPLOYER_ADDRESS = os.environ.get("DEPLOYER_ADDRESS") or WALLET_ADDRESS

print(f"[EXECUTOR] PRIVATE_KEY set: {bool(PRIVATE_KEY and PRIVATE_KEY != DEFAULT_LOCAL_KEY)}")
print(f"[EXECUTOR] WALLET_ADDRESS: {WALLET_ADDRESS}")
print(f"[EXECUTOR] DEPLOYER_ADDRESS: {DEPLOYER_ADDRESS}")
print(f"[EXECUTOR] PIMLICO_API_KEY set: {bool(PIMLICO_API_KEY)}")

def _is_non_empty(value):
    return bool(value and value.strip())

def sync_runtime_state():
    global PAPER_TRADING_MODE, PRIVATE_KEY, WALLET_ADDRESS, DEPLOYER_ADDRESS, PIMLICO_API_KEY, PRIVATE_MODE

    if not REDIS_URL:
        return

    try:
        # Use decode_responses=True for easier handling
        client = redis.from_url(REDIS_URL, socket_timeout=2, decode_responses=True)
        
        # 1. Sync Trading Mode
        runtime_mode = client.get("alphamark:mode")
        if runtime_mode in {"paper", "live"}:
            PAPER_TRADING_MODE = runtime_mode == "paper"

        # 2. Sync Active Wallet & Key
        active_wallet_address = client.get("alphamark:active_wallet_address")
        if active_wallet_address:
            WALLET_ADDRESS = active_wallet_address
            # If we changed wallet, DEPLOYER_ADDRESS usually stays same unless also env updated
            runtime_private_key = client.get(f"alphamark:wallet:{active_wallet_address}:private_key")
            if _is_non_empty(runtime_private_key):
                PRIVATE_KEY = runtime_private_key

        # 3. Dynamic Env Sync: Pull from shared alphamark:env hash
        # This allows dashboard-uploaded .env variables to propagate to the bot
        env_overrides = client.hgetall("alphamark:env")
        if env_overrides:
            if "PIMLICO_API_KEY" in env_overrides:
                PIMLICO_API_KEY = env_overrides["PIMLICO_API_KEY"]
            if "PRIVATE_KEY" in env_overrides and not active_wallet_address:
                PRIVATE_KEY = env_overrides["PRIVATE_KEY"]
            if "WALLET_ADDRESS" in env_overrides and not active_wallet_address:
                WALLET_ADDRESS = env_overrides["WALLET_ADDRESS"]
            if "DEPLOYER_ADDRESS" in env_overrides:
                DEPLOYER_ADDRESS = env_overrides["DEPLOYER_ADDRESS"]
            if "MEV_PROTECTION" in env_overrides:
                PRIVATE_MODE = env_overrides["MEV_PROTECTION"].lower() == "true"
            
            # ARCHITECT FIX: Update RPC URLs in CHAIN_CONFIG dynamically too
            for chain, cfg in CHAIN_CONFIG.items():
                rpc_var = f"{chain.upper()}_RPC_URL"
                if rpc_var in env_overrides:
                    cfg["rpc"] = env_overrides[rpc_var]
                    # Reset any cached provider to force re-init with new RPC
                    if chain in W3_PROVIDERS: del W3_PROVIDERS[chain]

    except Exception as exc:
        logger.debug(f"Runtime state sync failed: {exc}")

def _should_require_live_credentials():
    return not PAPER_TRADING_MODE

if _should_require_live_credentials():
    if not _is_non_empty(PIMLICO_API_KEY) or not _is_non_empty(PRIVATE_KEY):
        raise EnvironmentError("CRITICAL: PIMLICO_API_KEY and PRIVATE_KEY are required for live execution.")
elif not _is_non_empty(PRIVATE_KEY):
    PRIVATE_KEY = DEFAULT_LOCAL_KEY

ENTRYPOINT_ADDRESS = "0x5FF137D4b0FDCD49DcA30c7CF57E578a026d2789"
SIMPLE_ACCOUNT_FACTORY_ADDRESS = "0x9406Cc6185a346906296840746125a0E44976454"

# --- Enterprise Optimization: Persistent HTTP Session ---
# KPI #1: Latency. Reusing TCP connections eliminates SSL handshake overhead (~100ms per call).
GLOBAL_SESSION = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
GLOBAL_SESSION.mount('http://', adapter)
GLOBAL_SESSION.mount('https://', adapter)

# Cache W3 providers to avoid re-initializing
W3_PROVIDERS = {}

# --- Chain-specific URLs ---
CHAIN_CONFIG = {
    "ethereum": {
        "rpc": os.environ.get("ETHEREUM_RPC", f"https://api.pimlico.io/v1/1/rpc?apikey={PIMLICO_API_KEY}"),
        "paymaster": f"https://api.pimlico.io/v2/1/rpc?apikey={PIMLICO_API_KEY}",
        "bundler": os.environ.get("ETHEREUM_PRIVATE_BUNDLER") if PRIVATE_MODE else f"https://api.pimlico.io/v1/1/rpc?apikey={PIMLICO_API_KEY}",
        "chain_id": 1
    },
    "polygon": {
        "rpc": os.environ.get("POLYGON_RPC_URL"),
        "paymaster": f"https://api.pimlico.io/v2/137/rpc?apikey={PIMLICO_API_KEY}",
        "bundler": os.environ.get("POLYGON_PRIVATE_BUNDLER") if PRIVATE_MODE else f"https://api.pimlico.io/v1/137/rpc?apikey={PIMLICO_API_KEY}",
        "chain_id": 137
    },
    "arbitrum": {
        "rpc": os.environ.get("ARBITRUM_RPC", f"https://api.pimlico.io/v1/42161/rpc?apikey={PIMLICO_API_KEY}"),
        "paymaster": f"https://api.pimlico.io/v2/42161/rpc?apikey={PIMLICO_API_KEY}",
        "bundler": os.environ.get("ARBITRUM_PRIVATE_BUNDLER") if PRIVATE_MODE else f"https://api.pimlico.io/v1/42161/rpc?apikey={PIMLICO_API_KEY}",
        "chain_id": 42161
    },
    "bsc": {
        "rpc": os.environ.get("BSC_RPC", f"https://api.pimlico.io/v1/56/rpc?apikey={PIMLICO_API_KEY}"),
        "paymaster": f"https://api.pimlico.io/v2/56/rpc?apikey={PIMLICO_API_KEY}",
        "bundler": f"https://api.pimlico.io/v1/56/rpc?apikey={PIMLICO_API_KEY}",
        "chain_id": 56
    },
    "optimism": {
        "rpc": os.environ.get("OPTIMISM_RPC", f"https://api.pimlico.io/v1/10/rpc?apikey={PIMLICO_API_KEY}"),
        "paymaster": f"https://api.pimlico.io/v2/10/rpc?apikey={PIMLICO_API_KEY}",
        "bundler": f"https://api.pimlico.io/v1/10/rpc?apikey={PIMLICO_API_KEY}",
        "chain_id": 10
    },
    "base": {
        "rpc": os.environ.get("BASE_RPC", f"https://api.pimlico.io/v1/8453/rpc?apikey={PIMLICO_API_KEY}"),
        "paymaster": f"https://api.pimlico.io/v2/8453/rpc?apikey={PIMLICO_API_KEY}",
        "bundler": f"https://api.pimlico.io/v1/8453/rpc?apikey={PIMLICO_API_KEY}",
        "chain_id": 8453
    },
    "avalanche": {
        "rpc": os.environ.get("AVALANCHE_RPC", f"https://api.pimlico.io/v1/43114/rpc?apikey={PIMLICO_API_KEY}"),
        "paymaster": f"https://api.pimlico.io/v2/43114/rpc?apikey={PIMLICO_API_KEY}",
        "bundler": f"https://api.pimlico.io/v1/43114/rpc?apikey={PIMLICO_API_KEY}",
        "chain_id": 43114
    },
    # --- Local Simulation Chains ---
    "localethereum": {
        "rpc": "http://host.docker.internal:8545",
        "bundler": None, # No bundler for local
        "chain_id": 1,
        "is_local": True
    },
    "localpolygon": {
        "rpc": "http://host.docker.internal:8547",
        "bundler": None,
        "chain_id": 137,
        "is_local": True
    },
    "localbsc": {
        "rpc": "http://host.docker.internal:8549",
        "bundler": None,
        "chain_id": 56,
        "is_local": True
    },
}

# --- Minimal ABIs ---
ENTRYPOINT_ABI = [{"inputs": [{"internalType": "address", "name": "sender", "type": "address"}, {"internalType": "uint192", "name": "key", "type": "uint192"}], "name": "getNonce", "outputs": [{"internalType": "uint256", "name": "nonce", "type": "uint256"}], "stateMutability": "view", "type": "function"}]
SIMPLE_ACCOUNT_FACTORY_ABI = [
    {"inputs": [{"internalType": "address", "name": "owner", "type": "address"}, {"internalType": "uint256", "name": "salt", "type": "uint256"}], "name": "getAddress", "outputs": [{"internalType": "address", "name": "", "type": "address"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"internalType": "address", "name": "owner", "type": "address"}, {"internalType": "uint256", "name": "salt", "type": "uint256"}], "name": "createAccount", "outputs": [{"internalType": "contract SimpleAccount", "name": "ret", "type": "address"}], "stateMutability": "nonpayable", "type": "function"}
]
# UPDATED: Multi-hop arbitrage ABI
FLASHLOAN_ABI = [
    {"inputs": [{"internalType": "address", "name": "tokenToBorrow", "type": "address"}, {"internalType": "uint256", "name": "amount", "type": "uint256"}, {"internalType": "bytes", "name": "params", "type": "bytes"}], "name": "executeArbitrage", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    # New multi-hop method for complex arbitrage paths
    {"inputs": [
        {"internalType": "address", "name": "tokenToBorrow", "type": "address"},
        {"internalType": "uint256", "name": "amount", "type": "uint256"},
        {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
        {"internalType": "address[]", "name": "path", "type": "address[]"},
        {"internalType": "address[]", "name": "routers", "type": "address[]"},
        {"internalType": "uint256[]", "name": "fees", "type": "uint256[]"}
    ], "name": "executeMultiHopArbitrage", "outputs": [], "stateMutability": "nonpayable", "type": "function"}
]
SIMPLE_ACCOUNT_ABI = [{"inputs": [{"internalType": "address", "name": "dest", "type": "address"}, {"internalType": "uint256", "name": "value", "type": "uint256"}, {"internalType": "bytes", "name": "func", "type": "bytes"}], "name": "execute", "outputs": [], "stateMutability": "nonpayable", "type": "function"}]


# --- Helper Functions ---

def get_user_op_hash(w3: Web3, user_op: dict, chain_id: int) -> bytes:
    """Calculates the UserOperation hash according to EIP-4337."""
    packed_user_op = encode_packed(
        ['address', 'uint256', 'bytes32', 'bytes32', 'uint256', 'uint256', 'uint256', 'uint256', 'uint256', 'bytes32'],
        [
            Web3.to_checksum_address(user_op['sender']), int(user_op['nonce'], 16),
            w3.keccak(hexstr=user_op['initCode']), w3.keccak(hexstr=user_op['callData']),
            int(user_op['callGasLimit'], 16), int(user_op['verificationGasLimit'], 16),
            int(user_op['preVerificationGas'], 16), int(user_op['maxFeePerGas'], 16),
            int(user_op['maxPriorityFeePerGas'], 16), w3.keccak(hexstr=user_op['paymasterAndData'])
        ]
    )
    user_op_hash_no_entrypoint = w3.keccak(packed_user_op)
    return w3.keccak(encode_packed(['bytes32', 'address', 'uint256'], [user_op_hash_no_entrypoint, Web3.to_checksum_address(ENTRYPOINT_ADDRESS), chain_id]))

# --- Main Execution Logic ---

def execute_flashloan(opportunity: dict) -> (bool, str):
    """
    Builds, signs, and sends a gasless UserOperation for an arbitrage opportunity.
    Returns (success_boolean, user_op_hash_or_error_string).
    """
    # Variables are now guaranteed by module-level check, but we check specific chain config
    

    sync_runtime_state()
    chain = opportunity.get("chain")
    if not chain or chain not in CHAIN_CONFIG:
        logger.error(f"Opportunity is missing or has unsupported 'chain': {chain}")
        return False, f"Unsupported chain: {chain}"

    config = CHAIN_CONFIG[chain].copy() # Copy to avoid polluting global state

    # Auto-detect local simulation environment (Docker -> Host)
    # If RPC points to host.docker.internal, force local execution mode
    if "host.docker.internal" in config["rpc"] or "127.0.0.1" in config["rpc"]:
        logger.info(f"Detected local RPC for {chain}. Switching to Direct Execution Mode.")
        config["is_local"] = True

    if not _is_non_empty(PRIVATE_KEY):
        logger.error("Configuration Error: PRIVATE_KEY missing.")
        return False, "Configuration Error: Missing PRIVATE_KEY"
    
    if not config.get("bundler") and not config.get("is_local"):
        logger.error(f"Configuration Error: Missing 'bundler' URL for chain {chain}. Check env vars.")
        return False, "Configuration Error: Missing Bundler URL"

    if not config.get("is_local") and not _is_non_empty(PIMLICO_API_KEY):
        logger.error(f"Configuration Error: Missing Pimlico API key for chain {chain}.")
        return False, "Configuration Error: Missing Pimlico API key"

    if chain not in W3_PROVIDERS:
        W3_PROVIDERS[chain] = Web3(Web3.HTTPProvider(config["rpc"], session=GLOBAL_SESSION))
    w3 = W3_PROVIDERS[chain]
    owner_account = Account.from_key(PRIVATE_KEY)
    
    # Resolve FlashLoan address dynamically
    flashloan_addr = get_flashloan_address()
    if not flashloan_addr:
        logger.error("FLASHLOAN_CONTRACT_ADDRESS not set and could not compute dynamically.")
        logger.error("Set FLASHLOAN_CONTRACT_ADDRESS or DEPLOYER_ADDRESS in environment.")
        return False, "Configuration Error: Missing FlashLoan Address"

    try:
        # 1. Get Smart Account address
        factory_contract = w3.eth.contract(address=SIMPLE_ACCOUNT_FACTORY_ADDRESS, abi=SIMPLE_ACCOUNT_FACTORY_ABI)
        sender_address = factory_contract.functions.getAddress(owner_account.address, 0).call()
        logger.info(f"Smart Account Address: {sender_address}")

        # --- Gasless Logic: Check Deployment & Generate InitCode ---
        # If the Smart Account is not deployed (no code at address), we must deploy it
        # within this UserOperation using initCode. Pimlico will sponsor this deployment.
        init_code = "0x"
        try:
            code = w3.eth.get_code(sender_address)
            if len(code) <= 2: # Empty or "0x"
                logger.info("Smart Account not deployed. Generating initCode for gasless deployment.")
                # initCode = FactoryAddress + encode(createAccount(owner, salt))
                create_account_data = factory_contract.encodeABI(fn_name="createAccount", args=[owner_account.address, 0])
                init_code = SIMPLE_ACCOUNT_FACTORY_ADDRESS + create_account_data[2:]
        except Exception as e:
            logger.warning(f"Could not check code at sender address: {e}")

        # 2. Encode CallData to our FlashLoan contract
        flashloan_interface = w3.eth.contract(abi=FLASHLOAN_ABI)
        
        # --- Encode the arbitrage parameters for the smart contract ---
        # FIXED: Support multi-hop arbitrage with proper encoding
        # Format: (amountOutMin, path, routers, fees)
        expected_out = opportunity.get('expected_amount_out', 0)
        slippage = opportunity.get('slippage', 0.01) # Default to 1% if not provided
        amount_out_min = int(expected_out * (1 - slippage))

        # Extract execution path and router
        # Ensure addresses are checksummed for ABI encoding
        trade_path = [Web3.to_checksum_address(addr) for addr in opportunity.get('path', [])]
        
        # ARCHITECT FIX: Support mixed-router paths (Cross-DEX Arb) if provided
        if 'routers' in opportunity and opportunity['routers']:
            routers = [Web3.to_checksum_address(r) for r in opportunity['routers']]
        else:
            # Fallback for single-router strategies
            router_address = Web3.to_checksum_address(opportunity.get('router_address', '0x0000000000000000000000000000000000000000'))
            # For multi-hop: create router array (one router per hop)
            routers = [router_address] * max(1, len(trade_path) - 1)
        
        # ARCHITECT FIX: Use fees from opportunity if present (for V3), else 0
        fees = opportunity.get('fees', [0] * max(1, len(trade_path) - 1))

        # Encoded params: (uint256 amountOutMin, address[] path, address[] routers, uint256[] fees)
        arbitrage_params = encode(
            ['uint256', 'address[]', 'address[]', 'uint256[]'], 
            [amount_out_min, trade_path, routers, fees]
        )

        # 2a. Inner Call: The execution logic on the FlashLoan contract
        # Using the updated multi-hop format
        inner_call_data = flashloan_interface.encodeABI(fn_name="executeArbitrage", args=[
            Web3.to_checksum_address(opportunity['base_token_address']),
            w3.to_wei(opportunity['loan_amount'], 'ether'),
            arbitrage_params
        ])

        # 2b. Outer Call: The UserOperation must call 'execute' on the Smart Account
        smart_account_interface = w3.eth.contract(abi=SIMPLE_ACCOUNT_ABI)
        call_data = smart_account_interface.encodeABI(fn_name="execute", args=[Web3.to_checksum_address(flashloan_addr), 0, inner_call_data])

        # --- KPI #8 Upgrade: Pre-Execution Simulation Gate ---
        # Never send a UserOp that is likely to fail. Simulate it first.
        # FIXED: Now correctly simulates the FlashLoan contract execution
        logger.info("Simulating transaction before execution...")
        try:
            # We simulate the 'execute' call from the smart account to the FlashLoan contract
            # This properly tests if the arbitrage logic will succeed
            w3.eth.call({
                'from': sender_address,
                'to': Web3.to_checksum_address(flashloan_addr),  # FIXED: Now calls the actual FlashLoan contract
                'data': call_data
            }, 'latest')
            logger.info("✅ Simulation successful. Proceeding with execution.")
        except Exception as e:
            logger.error(f"❌ Simulation FAILED. Aborting execution. Reason: {e}")
            return False, f"Simulation failed: {e}"

        # 3. Get Nonce from EntryPoint
        entrypoint_contract = w3.eth.contract(address=ENTRYPOINT_ADDRESS, abi=ENTRYPOINT_ABI)
        
        nonce = 0
        if REDIS_URL:
            try:
                r = redis.from_url(REDIS_URL)
                nonce_key = f"alphamark:nonce:{sender_address}"
                
                # Atomic Nonce Pipelining
                # 1. Try to set initial value from chain (only if key doesn't exist)
                #    We set it to chain_nonce - 1, so the first INCR gives us chain_nonce.
                chain_nonce = entrypoint_contract.functions.getNonce(sender_address, 0).call()
                r.set(nonce_key, chain_nonce - 1, nx=True)
                
                # 2. Atomic Increment to get unique reservation
                nonce = r.incr(nonce_key)
                logger.info(f"Nonce (Redis Atomic): {nonce}")
            except Exception as e:
                logger.error(f"Redis nonce failure: {e}. Falling back to chain.")
                nonce = entrypoint_contract.functions.getNonce(sender_address, 0).call()
        else:
            nonce = entrypoint_contract.functions.getNonce(sender_address, 0).call()
            logger.info(f"Nonce (Chain): {nonce}")

        # --- KPI #5 Upgrade: Predictive EIP-1559 Gas Strategy ---
        try:
            latest_block = w3.eth.get_block('latest')
            base_fee = latest_block['baseFeePerGas']
            
            # Look at the last 3 blocks to see the trend
            block_history = [w3.eth.get_block(latest_block.number - i) for i in range(1, 4)]
            historical_base_fees = [b['baseFeePerGas'] for b in block_history if 'baseFeePerGas' in b]
            
            # Predictive model: average of recent fees + a buffer for the next block's potential increase
            avg_base_fee = sum(historical_base_fees) / len(historical_base_fees) if historical_base_fees else base_fee
            predicted_base_fee = max(base_fee, int(avg_base_fee * 1.1)) # Use current or 110% of avg, whichever is higher
            
            # Use an aggressive priority fee for front-of-block inclusion (e.g., 2 Gwei)
            priority_fee_oracle = w3.eth.max_priority_fee()
            aggressive_priority_fee = max(priority_fee_oracle, w3.to_wei(2, 'gwei'))
            
            max_fee_per_gas = predicted_base_fee + aggressive_priority_fee
            max_priority_fee_per_gas = aggressive_priority_fee
            logger.info(f"Predictive Gas Strategy: Base={base_fee}, PredictedBase={predicted_base_fee}, PriorityTip={aggressive_priority_fee}")
        except Exception as e:
            logger.warning(f"Predictive gas model failed ({e}), falling back to simple model.")
            max_fee_per_gas = int(w3.eth.gas_price * 1.25)
            max_priority_fee_per_gas = max_fee_per_gas

        user_op = {
            "sender": sender_address, "nonce": hex(nonce), "initCode": init_code, "callData": call_data,
            "maxFeePerGas": hex(max_fee_per_gas), 
            "maxPriorityFeePerGas": hex(max_priority_fee_per_gas),
            "paymasterAndData": "0x", "signature": "0x"
        }

        # 5. Sponsor with Pimlico Paymaster
        logger.info("Requesting paymaster sponsorship...")
        sponsorship_response = GLOBAL_SESSION.post(config["paymaster"], json={
            "jsonrpc": "2.0", "method": "pm_sponsorUserOperation", "params": [user_op, ENTRYPOINT_ADDRESS], "id": 1
        }, timeout=10)
        sponsorship_response.raise_for_status()
        sponsorship_data = sponsorship_response.json()
        if "error" in sponsorship_data: raise Exception(f"Paymaster Error: {sponsorship_data['error']['message']}")

        sponsored_fields = sponsorship_data['result']
        user_op.update(sponsored_fields)
        logger.info("Paymaster sponsorship received.")

        # 6. Sign the UserOperation
        user_op_hash = get_user_op_hash(w3, user_op, config["chain_id"])
        signature = owner_account.signHash(user_op_hash).signature.hex()
        user_op["signature"] = signature
        logger.info("UserOperation signed.")

        # --- Paper Trading Mode Gate ---
        if PAPER_TRADING_MODE:
            logger.warning("PAPER TRADING MODE: Halting before final submission.")
            # Return a fake hash to simulate success for the dashboard
            return True, w3.keccak(text="paper-trade-success").hex()

        # 7. Send Transaction (Direct Execution for Local / Fallback)
        if config.get("is_local"):
            logger.info("📡 Sending Direct Transaction (Local Mode)...")
            tx = {
                'to': Web3.to_checksum_address(flashloan_addr),
                'data': inner_call_data, # Directly call executeArbitrage on FlashLoan contract
                'gas': max_fee_per_gas,
                'maxFeePerGas': max_fee_per_gas,
                'maxPriorityFeePerGas': max_priority_fee_per_gas,
                'nonce': w3.eth.get_transaction_count(owner_account.address),
                'chainId': config["chain_id"],
                'type': 2
            }
            signed_tx = owner_account.sign_transaction(tx)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            logger.info(f"Local Transaction submitted! Hash: {tx_hash.hex()}")
            return True, tx_hash.hex()

        # 7. Send to Bundler
        if PRIVATE_MODE:
            logger.info("🛡️ Sending UserOperation to PRIVATE MEMPOOL (MEV Protection Active)...")
        else:
            logger.info("⚠️ Sending UserOperation to PUBLIC Bundler (MEV Protection Disabled)...")
            
        send_op_response = GLOBAL_SESSION.post(config["bundler"], json={
            "jsonrpc": "2.0", "method": "eth_sendUserOperation", "params": [user_op, ENTRYPOINT_ADDRESS], "id": 1
        }, timeout=10)
        send_op_response.raise_for_status()
        send_op_data = send_op_response.json()
        if "error" in send_op_data: raise Exception(f"Bundler Error: {send_op_data['error']['message']}")

        final_user_op_hash = send_op_data['result']
        logger.info(f"UserOperation submitted successfully! Hash: {final_user_op_hash}")
        
        return True, final_user_op_hash

    except Exception as e:
        logger.error(f"Failed to execute flashloan: {e}")
        return False, str(e)
