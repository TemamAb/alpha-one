"""
FlashLoan Contract Deployment Utilities
Provides functions to compute contract addresses before deployment.
"""

import os
import json
from web3 import Web3
from eth_abi import encode
from eth_utils import keccak, rlp_encode, normalize_address


def compute_contract_address(sender_address: str, nonce: int) -> str:
    """
    Compute the address where a contract will be deployed.
    
    Args:
        sender_address: The address deploying the contract (checksummed)
        nonce: The nonce of the sender (transaction count)
    
    Returns:
        The computed contract address
    """
    sender = Web3.to_checksum_address(sender_address)
    
    # RLP encode the sender and nonce
    # For EOA -> Contract: [sender, nonce]
    rlp_data = rlp_encode([sender, nonce])
    
    # Keccak256 hash
    hash_bytes = keccak(rlp_data)
    
    # Last 20 bytes is the address
    address_bytes = hash_bytes[-20:]
    return Web3.to_checksum_address(address_bytes.hex())


def compute_contract_address_via_create2(sender_address: str, salt: int, bytecode_hash: str) -> str:
    """
    Compute address for CREATE2 deployment.
    
    Args:
        sender_address: The address deploying via CREATE2
        salt: Salt value used in CREATE2
        bytecode_hash: Keccak256 hash of the creation bytecode
    
    Returns:
        The computed CREATE2 address
    """
    sender = Web3.to_checksum_address(sender_address)
    
    # CREATE2 address computation: keccak256(0xff + sender + salt + bytecode_hash)
    create2_input = b'\xff' + bytes.fromhex(sender[2:]) + salt.to_bytes(32, 'big') + bytes.fromhex(bytecode_hash[2:])
    hash_bytes = keccak(create2_input)
    
    # Last 20 bytes is the address
    address_bytes = hash_bytes[-20:]
    return Web3.to_checksum_address(address_bytes.hex())


def get_deployer_nonce(w3: Web3, deployer_address: str) -> int:
    """
    Get the current nonce of the deployer address.
    
    Args:
        w3: Web3 instance
        deployer_address: The deployer address
    
    Returns:
        Current nonce (transaction count)
    """
    return w3.eth.get_transaction_count(Web3.to_checksum_address(deployer_address))


def predict_flashloan_address(w3: Web3, deployer_address: str) -> str:
    """
    Predict the FlashLoan contract address before deployment.
    
    Uses the current nonce of the deployer to predict where the 
    contract will be deployed.
    
    Args:
        w3: Web3 instance
        deployer_address: The account that will deploy the contract
    
    Returns:
        Predicted contract address
    """
    deployer = Web3.to_checksum_address(deployer_address)
    nonce = get_deployer_nonce(w3, deployer)
    return compute_contract_address(deployer, nonce)


def get_flashloan_addresses_for_chain(chain_rpc: str, deployer_address: str, num_addresses: int = 5):
    """
    Get a list of potential FlashLoan addresses for a given chain.
    Useful for preparing configuration for multiple possible deployment nonces.
    
    Args:
        chain_rpc: RPC URL for the chain
        deployer_address: The account that will deploy the contract
        num_addresses: Number of future addresses to generate
    
    Returns:
        List of potential addresses with their nonces
    """
    w3 = Web3(Web3.HTTPProvider(chain_rpc))
    if not w3.is_connected():
        raise ConnectionError(f"Failed to connect to {chain_rpc}")
    
    deployer = Web3.to_checksum_address(deployer_address)
    current_nonce = get_deployer_nonce(w3, deployer)
    
    addresses = []
    for i in range(num_addresses):
        addr = compute_contract_address(deployer, current_nonce + i)
        addresses.append({
            'nonce': current_nonce + i,
            'address': addr
        })
    
    return addresses


def load_chain_config(chain_name: str) -> dict:
    """Load chain configuration from contracts.json"""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        '..', 'config_asset_registry', 'data', 'contracts.json'
    )
    
    with open(config_path) as f:
        config = json.load(f)
    
    return config.get(chain_name, {})


def predict_addresses_for_all_chains(deployer_address: str, rpc_env_var: str = 'ETH_RPC_URL'):
    """
    Predict FlashLoan addresses for all configured chains.
    
    Args:
        deployer_address: The deployer wallet address
        rpc_env_var: Environment variable containing RPC URL
    
    Returns:
        Dictionary mapping chain names to predicted addresses
    """
    rpc_url = os.environ.get(rpc_env_var)
    if not rpc_url:
        # Try alternative env vars
        rpc_url = os.environ.get('ETHEREUM_RPC')
    
    if not rpc_url:
        raise ValueError(f"No RPC URL found. Set {rpc_env_var} or ETHEREUM_RPC")
    
    # For each chain, we need the specific RPC
    # This is a simplified version - in production you'd iterate through all chains
    chains = ['ethereum', 'polygon', 'arbitrum', 'optimism', 'bsc']
    
    results = {}
    for chain in chains:
        try:
            rpc = os.environ.get(f'{chain.upper()}_RPC_URL')
            if rpc:
                w3 = Web3(Web3.HTTPProvider(rpc))
                if w3.is_connected():
                    addr = predict_flashloan_address(w3, deployer_address)
                    results[chain] = addr
        except Exception as e:
            print(f"Warning: Could not predict address for {chain}: {e}")
    
    return results


# CLI for testing
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python deploy.py <deployer_address> <rpc_url>")
        sys.exit(1)
    
    deployer = sys.argv[1]
    rpc = sys.argv[2]
    
    w3 = Web3(Web3.HTTPProvider(rpc))
    if not w3.is_connected():
        print(f"Failed to connect to {rpc}")
        sys.exit(1)
    
    predicted = predict_flashloan_address(w3, deployer)
    current_nonce = w3.eth.get_transaction_count(deployer)
    
    print(f"Deployer: {deployer}")
    print(f"Current Nonce: {current_nonce}")
    print(f"Predicted FlashLoan Address: {predicted}")
    print(f"\nSet in your environment:")
    print(f"FLASHLOAN_CONTRACT_ADDRESS={predicted}")
