# MEV executor - Fixed version
import requests
from web3 import Web3
import json
import os
import logging

logger = logging.getLogger(__name__)

# Flashbots relay endpoints (updated to current v2 API)
FLASHBOTS_RELAY_V2 = "https://relay.flashbots.net"
MEV_BUILDER_URLS = {
    "ethereum": [
        "https://relay.flashbots.net",
        "https://builder0x77.io",
        "https://rpc.mevblocker.io",
        "https://rpc.mevboost.org"
    ],
    "polygon": [
        "https://rpc.flashbots.net/fast",
        "https://polygon-builder.r水下.to"  # Flashbots Polygon
    ],
    "bsc": [
        "https://rpc.mevblocker.io"
    ],
    "arbitrum": [
        "https://relay.flashbots.net"
    ],
    "optimism": [
        "https://relay.flashbots.net"
    ]
}

# ERC20 ABI for token transfers
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    }
]

# FlashLoan ABI (minimal for execution)
FLASHLOAN_ABI = [
    {
        "inputs": [
            {"name": "tokenToBorrow", "type": "address"},
            {"name": "amount", "type": "uint256"},
            {"name": "params", "type": "bytes"}
        ],
        "name": "executeArbitrage",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

def execute_mev(chain, opportunity):
    """
    Execute MEV bundle with flashloan arbitrage.
    Sends private tx bundle to builders to prevent front-running.
    """
    private_key = os.environ.get("PRIVATE_KEY")
    if not private_key:
        logger.error("PRIVATE_KEY required for MEV")
        return False
    
    rpc_url = opportunity.get('rpc', os.environ.get(f"{chain.upper()}_RPC", "https://mainnet.infura.io/v3/YOUR_KEY"))
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    
    if not w3.is_connected():
        logger.error(f"Failed to connect to RPC: {rpc_url}")
        return False
    
    account = w3.eth.account.from_key(private_key)
    
    # Build flashloan tx
    flash_tx = build_flash_tx(w3, opportunity, account)
    if not flash_tx:
        return False
    
    # Create bundle
    bundle = [{
        "signedTransaction": flash_tx.rawTransaction.hex()
    }]
    
    # Send to MEV relays/builders
    success = False
    for url in MEV_BUILDER_URLS.get(chain, MEV_BUILDER_URLS["ethereum"]):
        try:
            # Try Flashbots v2 API
            resp = requests.post(
                f"{url}/relay/bundle", 
                json={"version": "v0.1", "body": bundle},
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            if resp.status_code == 200:
                logger.info(f"MEV bundle accepted by {url}")
                success = True
                break
            else:
                logger.warning(f"Builder {url} returned {resp.status_code}: {resp.text}")
        except requests.exceptions.RequestException as e:
            logger.warning(f"Builder {url} failed: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error with {url}: {e}")
    
    if not success:
        # Fallback to public mempool
        logger.warning("Falling back to public mempool")
        try:
            tx_hash = w3.eth.send_raw_transaction(flash_tx.rawTransaction)
            logger.info(f"Public mempool tx: {tx_hash.hex()}")
            return True
        except Exception as e:
            logger.error(f"Failed to send public tx: {e}")
            return False
    
    return success

def build_flash_tx(w3, opp, account):
    """
    Build signed flashloan tx
    """
    try:
        # Get flashloan contract address from environment
        flashloan_address = os.environ.get("FLASHLOAN_CONTRACT_ADDRESS")
        if not flashloan_address:
            logger.error("FLASHLOAN_CONTRACT_ADDRESS not set in environment!")
            return None  # Fail explicitly instead of using invalid address
        
        # Parse opportunity parameters
        token = opp.get('base_token_address', opp.get('token', "0x0000000000000000000000000000000000000000"))
        loan_amount = opp.get('loan_amount', 1.0)
        path = opp.get('path', [])
        router_address = opp.get('router_address', "0x0000000000000000000000000000000000000000")
        
        # Calculate amount out min with slippage
        expected_out = opp.get('expected_amount_out', 0)
        slippage = opp.get('slippage', 0.01)
        amount_out_min = int(expected_out * (1 - slippage))
        
        # Build params for multi-hop
        # Format: (amountOutMin, path, routers, fees)
        routers = [router_address] * (len(path) - 1) if len(path) > 1 else [router_address]
        fees = [0] * (len(path) - 1)  # V2 fees = 0
        
        from eth_abi import encode
        params = encode(
            ['uint256', 'address[]', 'address[]', 'uint256[]'],
            [amount_out_min, path, routers, fees]
        )
        
        # Build transaction
        contract = w3.eth.contract(address=flashloan_address, abi=FLASHLOAN_ABI)
        
        tx = contract.functions.executeArbitrage(
            token,
            w3.to_wei(loan_amount, 'ether'),
            params
        ).build_transaction({
            'from': account.address,
            'gas': 1500000,  # Increased for multi-hop
            'maxFeePerGas': w3.to_wei('50', 'gwei'),
            'maxPriorityFeePerGas': w3.to_wei('2', 'gwei'),
            'nonce': w3.eth.get_transaction_count(account.address),
            'type': 2  # EIP-1559
        })
        
        return w3.eth.account.sign_transaction(tx, private_key=account.key)
        
    except Exception as e:
        logger.error(f"Failed to build flash tx: {e}")
        return None
