#!/usr/bin/env python3
import sys
sys.path.append('strategy_engine/src')
from strategy import find_cross_chain_opportunities
from utils import get_price
print('Testing production price fetch...')
opps = find_cross_chain_opportunities()
print(f'Found {len(opps)} opportunities')
for opp in opps:
  print(opp)
