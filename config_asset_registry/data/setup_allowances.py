import os
import sys
import json
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

FLASHLOAN_ADDRESS = os.environ.get("FLASHLOAN_CONTRACT_ADDRESS")
PRIVATE_KEY = os.environ.get("PRIVATE_KEY")
RPC_URL = os.environ.get("POLYGON_RPC_URL") 

if not FLASHLOAN_ADDRESS or not PRIVATE_KEY or not RPC_URL:
    print("❌ Missing config in .env (FLASHLOAN_CONTRACT_ADDRESS, PRIVATE_KEY, RPC_URL)")
    sys.exit(1)

# Minimal ABIs
FLASHLOAN_ABI = [{"inputs": [{"internalType": "address", "name": "_token", "type": "address"}, {"internalType": "address", "name": "_spender", "type": "address"}, {"internalType": "uint256", "name": "_amount", "type": "uint256"}], "name": "approveToken", "outputs": [], "stateMutability": "nonpayable", "type": "function"}]

def setup():
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    account = w3.eth.account.from_key(PRIVATE_KEY)
    contract = w3.eth.contract(address=FLASHLOAN_ADDRESS, abi=FLASHLOAN_ABI)
    
    print(f"🔧 Configuring Allowances for {FLASHLOAN_ADDRESS}...")
    
    # Load config to get token and router addresses
    config_path = os.path.join(os.path.dirname(__file__), "..", "flashloan_app", "config_asset_registry", "data", "contracts.json")
    with open(config_path) as f:
        config = json.load(f)
        
    chain_data = config.get("polygon") # Targeting Polygon
    if not chain_data:
        print("Polygon config not found")
        return

    routers = chain_data.get("dexes", {}).values()
    # Common tokens on Polygon (WETH, USDC, USDT, WMATIC)
    tokens = [
        "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619", # WETH
        "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174", # USDC
        "0xc2132D05D31c914a87C6611C10748AEb04B58e8F", # USDT
        "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270"  # WMATIC
    ]

    nonce = w3.eth.get_transaction_count(account.address)

    for router in routers:
        for token in tokens:
            print(f"👉 Approving token {token[:6]}... for router {router[:6]}...")
            try:
                tx = contract.functions.approveToken(token, router, 2**256 - 1).build_transaction({
                    'from': account.address,
                    'nonce': nonce,
                    'gasPrice': int(w3.eth.gas_price * 1.1)
                })
                signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
                w3.eth.send_raw_transaction(signed.rawTransaction)
                print("   ✅ Sent!")
                nonce += 1
            except Exception as e:
                print(f"   ❌ Failed: {e}")

if __name__ == "__main__":
    setup()