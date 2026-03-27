import utils
import sys
sys.path.append('src')
from strategy import find_graph_arbitrage_opportunities, find_profitable_opportunities
import json

CONFIG = utils.CONFIG

print("=== GRAPH ARB TEST ===")

# Test graph for ethereum
chain = 'ethereum'
chain_data = CONFIG['ethereum']
opps = find_graph_arbitrage_opportunities(chain, chain_data)
print(f"Graph opps ethereum: {len(opps)}")

all_opps = find_profitable_opportunities()
print(f"Total opps: {len(all_opps)}")
print(json.dumps(all_opps, indent=2)[:1000] + "..." if all_opps else "No opps")
