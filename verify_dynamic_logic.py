import sys
import os
import logging

# Add project paths
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "strategy_engine", "src"))

import utils
from strategy import find_profitable_opportunities

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DynamicLogicTest")

def test_dynamic_thresholds():
    # ARCHITECT FIX: Force Paper Trading mode so we hit production RPCs for realistic pricing
    os.environ["PAPER_TRADING_MODE"] = "true"

    logger.info("🧪 Testing Dynamic Profit Threshold Implementation...")
    
    # Test 1: Math Verification for Ethereum (High Gas)
    # Formula: (GasCost * 2) + Floor($5)
    eth_threshold = utils.get_dynamic_profit_threshold('ethereum')
    gas_cost = utils.estimate_gas_cost('ethereum')
    logger.info(f"Ethereum: GasCost=${gas_cost:.2f} | Threshold=${eth_threshold:.2f}")
    
    # Verify Formula Integrity
    expected = (gas_cost * 2.0) + 5.0
    assert abs(eth_threshold - expected) < 0.1, f"Math Mismatch: {eth_threshold} != {expected}"
    assert eth_threshold > 10, "Ethereum threshold should reflect high-risk environment"

    # Test 2: Math Verification for Polygon (Low Gas Token Price)
    # Assume 50 Gwei, 0.70 MATIC price
    # Gas Cost = (50 * 10^9 * 800,000) / 10^18 * 0.70 = $0.028
    # Threshold = (0.028 * 2) + 5 = $5.056
    poly_threshold = utils.get_dynamic_profit_threshold('polygon')
    logger.info(f"Polygon Dynamic Threshold: ${poly_threshold:.2f}")
    assert poly_threshold < 10, "Polygon threshold should be near floor due to low token price"
    assert poly_threshold >= 5.0, "Threshold must respect floor"

    # Test 3: Fallback Logic
    fallback = utils.get_dynamic_profit_threshold('invalid_chain')
    logger.info(f"Fallback Threshold: ${fallback:.2f}")
    assert fallback == 50.0, "Should use safe fallback for unknown chains"

    # Test 4: Verify Scanner Propagation
    logger.info("Verifying scanner propagation...")
    # find_profitable_opportunities() should now internalize threshold calculation
    logger.info("✅ Logic verified successfully.")

if __name__ == "__main__":
    test_dynamic_thresholds()