#!/usr/bin/env python3
"""Quick test script to verify the strategy is working"""
import sys
import os

# Add the strategy_engine/src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'strategy_engine', 'src'))

from strategy import find_cross_chain_opportunities

print("=" * 50)
print("Testing AlphaMark Strategy...")
print("=" * 50)

opps = find_cross_chain_opportunities()
print(f"\n=== Found {len(opps)} opportunities ===")
for opp in opps:
    print(opp)
