import logging
import sys
import os

# Add project root to path to allow importing from other modules
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "strategy_engine", "src"))
# bot.py uses utils_fixed, but we only have utils.py. We assume it's the one to be used.
import utils

logger = logging.getLogger(__name__)

MAX_SLIPPAGE_PCT = 0.005  # 0.5%
MIN_LIQUIDITY_RATIO = 0.1  # 10% of pool
MIN_PROFIT_USD = 10  # USD equivalent
IMPERMANENT_LOSS_THRESHOLD = 0.02  # 2%

def check_slippage(expected_price, actual_price, max_pct=None):
    """
    Check if slippage exceeds threshold.
    Returns True if safe (low slippage).
    """
    if max_pct is None:
        max_pct = MAX_SLIPPAGE_PCT
    
    slippage = abs(actual_price - expected_price) / expected_price
    safe = slippage <= max_pct
    if not safe:
        logger.warning(f"High slippage: {slippage*100:.2f}% > {max_pct*100:.2f}%")
    return safe

def check_liquidity(amount_needed, pool_size, ratio=None):
    """
    Check if pool has enough liquidity for trade.
    amount_needed: tokens required
    pool_size: total pool liquidity
    """
    if ratio is None:
        ratio = MIN_LIQUIDITY_RATIO
    
    if pool_size <= 0:
        logger.warning("Pool size is 0 or negative - insufficient liquidity")
        return False
        
    has_liquidity = amount_needed <= pool_size * ratio
    if not has_liquidity:
        logger.warning(f"Low liquidity ratio: {amount_needed/pool_size:.2f} > {ratio}")
    return has_liquidity

def check_profit_threshold(gross_profit, fees, min_usd=None):
    """
    Verify net profit exceeds threshold.
    """
    if min_usd is None:
        min_usd = MIN_PROFIT_USD
    net_profit_usd = gross_profit - fees  # Assume USD normalized
    return net_profit_usd >= min_usd

def check_impermanent_loss(base_price, current_price, threshold=None):
    """
    Basic IL check for LP positions (if used).
    """
    if threshold is None:
        threshold = IMPERMANENT_LOSS_THRESHOLD
    il = abs(current_price - base_price) / base_price
    return il <= threshold

def full_risk_assessment(opportunity, current_prices, liquidity_data, model_confidence_score=None):
    """
    Comprehensive risk check combining all checks.
    FIXED: Now correctly maps opportunity dict keys to expected keys.
    
    Opportunity dict structure (from strategy):
    - type: str (e.g., "graph_arb", "cross_chain_arb")
    - chain: str
    - dex: str (single DEX name)
    - base_token: str (token symbol like "WETH")
    - base_token_address: str (token address)
    - path: list of addresses
    - router_address: str
    - loan_amount: float (in ETH/ Tokens)
    - expected_amount_out: int (wei)
    - profit_eth: float
    - net_usd_profit: float
    - slippage: float
    
    Returns (safe: bool, risks: list)
    """
    risks = []
    
    # FIXED: Use correct keys from opportunity dict
    # Slippage check - use the calculated slippage from opportunity
    slippage_pct = opportunity.get('slippage', 0)
    if slippage_pct > MAX_SLIPPAGE_PCT:
        risks.append(f"high_slippage:{slippage_pct*100:.2f}%")
    
    # FIXED: Liquidity check - use correct keys
    # Get the token from opportunity (handles both "token" and "base_token")
    token = opportunity.get('base_token', opportunity.get('token', 'WETH'))
    pool_liquidity_usd = liquidity_data.get(token, 0)
    
    # Calculate amount needed based on loan amount
    # loan_amount is in ETH, we need to convert to USD for comparison
    loan_amount_eth = opportunity.get('loan_amount', 0)
    
    # Convert loan amount to USD using a live price feed
    if loan_amount_eth > 0 and pool_liquidity_usd > 0:
        # Use a live oracle price instead of hardcoded or derived
        eth_price = utils.get_live_eth_price()
        
        loan_amount_usd = loan_amount_eth * eth_price
        
        # Check if loan is more than 10% of pool (our threshold)
        if not check_liquidity(loan_amount_usd, pool_liquidity_usd, MIN_LIQUIDITY_RATIO):
            risks.append("low_liquidity")
    
    # FIXED: Profit check - use correct keys (profit_eth, net_usd_profit)
    profit_eth = opportunity.get('profit_eth', 0)
    net_profit_usd = opportunity.get('net_usd_profit', 0)
    
    # Estimate fees (approximately 0.3% per swap * number of hops)
    path_length = len(opportunity.get('path', []))
    num_swaps = max(1, path_length - 1)
    estimated_fees_pct = 0.003 * num_swaps
    
    if net_profit_usd <= 0:
        risks.append("negative_profit")
    
    # Check minimum profit threshold
    if net_profit_usd < MIN_PROFIT_USD:
        risks.append(f"profit_below_threshold:${net_profit_usd:.2f}")
    
    # Check slippage against maximum allowed
    if slippage_pct > MAX_SLIPPAGE_PCT:
        risks.append(f"slippage_exceeds_limit:{slippage_pct*100:.2f}%")
    
    # Check if we have sufficient liquidity data
    if pool_liquidity_usd == 0:
        risks.append("unknown_liquidity")
    
    # Check ML Model Confidence (Self-Learning System)
    # If the AI is very unsure (< 50%), treat it as a risk
    if model_confidence_score is not None and model_confidence_score < 0.50:
        risks.append(f"low_ml_confidence:{model_confidence_score:.2f}")

    # Safe if no risks found
    safe = len(risks) == 0
    logger.info(f"Risk assessment: safe={safe}, risks={risks}")
    return safe, risks
