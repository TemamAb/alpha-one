#!/usr/bin/env python3
"""
Compute FlashLoan Contract Address
Dynamically calculates where the contract will be deployed.
"""
import os
import sys
from web3 import Web3
from eth_utils import keccak, rlp_encode

# Load environment
from dotenv import load_dotenv
load_dotenv()

def compute_contract_address(sender_address: str, nonce: int) -> str:
    """Compute address using CREATE formula"""
    sender = Web3.to_checksum_address(sender_address)
    rlp_data = rlp_encode([sender, nonce])
    hash_bytes = keccak(rlp_data)
    address_bytes = hash_bytes[-20:]
    return Web3.to_checksum_address(address_bytes.hex())

def main():
    # Get wallet from .env
    wallet_address = os.environ.get('WALLET_ADDRESS', '')
    if not wallet_address:
        print("ERROR: WALLET_ADDRESS not found in .env")
        sys.exit(1)
    
    print(f"Wallet Address: {wallet_address}")
    
    # Try multiple RPCs
    rpcs = [
        'https://eth.llamarpc.com',
        'https://api.pimlico.io/v1/1/rpc?apikey=' + os.environ.get('PIMLICO_API_KEY', ''),
        os.environ.get('ETHEREUM_RPC', ''),
    ]
    
    w3 = None
    for rpc in rpcs:
        if rpc:
            try:
                w3 = Web3(Web3.HTTPProvider(rpc))
                if w3.is_connected():
                    print(f"Connected via: {rpc[:50]}...")
                    break
            except:
                continue
    
    if not w3 or not w3.is_connected():
        print("ERROR: Could not connect to any Ethereum RPC")
        sys.exit(1)
    
    # Get current nonce
    nonce = w3.eth.get_transaction_count(wallet_address)
    print(f"Current nonce (transaction count): {nonce}")
    
    # Compute next contract addresses
    print("\n--- Potential Contract Addresses ---")
    for i in range(5):
        addr = compute_contract_address(wallet_address, nonce + i)
        # Check if contract exists at this address
        try:
            code = w3.eth.get_code(addr)
            has_code = len(code) > 2
            status = "DEPLOYED ✓" if has_code else "Empty"
        except:
            status = "Unknown"
        print(f"Nonce {nonce + i}: {addr} [{status}]")
    
    print("\n--- Environment Variables to Set ---")
    print(f"DEPLOYER_ADDRESS={wallet_address}")
    print(f"FLASHLOAN_CONTRACT_ADDRESS=<address from above if deployed>")
    print(f"CHAIN=ethereum")

if __name__ == "__main__":
    main()