#!/usr/bin/env python3
"""
Check wallet nonce and predict FlashLoan contract address
"""
from web3 import Web3

# Connect to Ethereum mainnet via free public RPC
w3 = Web3(Web3.HTTPProvider('https://eth.llamarpc.com'))

if not w3.is_connected():
    print("Failed to connect to Ethereum network")
    exit(1)

# Wallet from .env
WALLET_ADDRESS = "0x748Aa8ee067585F5bd02f0988eF6E71f2d662751"

# Get current nonce (transaction count)
nonce = w3.eth.get_transaction_count(WALLET_ADDRESS)
print(f"Wallet: {WALLET_ADDRESS}")
print(f"Current nonce (transactions sent): {nonce}")

# If nonce is 0, the first contract deployed would be at:
# address = keccak256(rlp([sender, nonce]))[12:]
# Let's compute what that address would be
from eth_utils import keccak, rlp_encode

def compute_contract_address(sender_address: str, nonce: int) -> str:
    sender = Web3.to_checksum_address(sender_address)
    rlp_data = rlp_encode([sender, nonce])
    hash_bytes = keccak(rlp_data)
    address_bytes = hash_bytes[-20:]
    return Web3.to_checksum_address(address_bytes.hex())

# Check if there's any code at potential contract addresses
for i in range(3):
    potential_addr = compute_contract_address(WALLET_ADDRESS, i)
    code = w3.eth.get_code(potential_addr)
    has_code = len(code) > 2
    print(f"Nonce {i}: {potential_addr} - {'HAS CODE' if has_code else 'Empty'}")

print(f"\n--- To deploy FlashLoan contract ---")
print(f"Run: npx hardhat run scripts/deploy.js --network ethereum")
print(f"Then set: FLASHLOAN_CONTRACT_ADDRESS=<deployed_address>")