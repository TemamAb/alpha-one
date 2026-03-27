#!/usr/bin/env python3
"""Test RPC connections"""

from web3 import Web3
import json
import os

# Get config path
config_path = os.path.join("config_asset_registry", "data", "contracts.json")

with open(config_path) as f:
    CONFIG = json.load(f)

chains = ['ethereum', 'polygon', 'bsc', 'arbitrum', 'optimism']

for chain in chains:
    print(f"\n=== {chain.upper()} ===")
    
    if chain not in CONFIG:
        print("  Not in config!")
        continue
    
    rpc = CONFIG[chain].get('rpc', 'NOT SET')
    fallback = CONFIG[chain].get('rpc_fallback', 'NOT SET')
    
    print(f"  Main RPC: {rpc[:50]}...")
    
    # Test main RPC
    try:
        w3 = Web3(Web3.HTTPProvider(rpc))
        if w3.is_connected():
            block = w3.eth.block_number
            print(f"  ✅ Main RPC WORKS! Block: {block}")
        else:
            print(f"  ❌ Main RPC not connected")
    except Exception as e:
        print(f"  ❌ Main RPC error: {e}")
    
    # Test fallback RPC
    if fallback and fallback != 'NOT SET':
        print(f"  Fallback: {fallback[:50]}...")
        try:
            w3_fb = Web3(Web3.HTTPProvider(fallback))
            if w3_fb.is_connected():
                block = w3_fb.eth.block_number
                print(f"  ✅ Fallback WORKS! Block: {block}")
            else:
                print(f"  ❌ Fallback not connected")
        except Exception as e:
            print(f"  ❌ Fallback error: {e}")
