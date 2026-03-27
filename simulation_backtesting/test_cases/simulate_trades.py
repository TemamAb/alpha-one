# Simulate trades
import json
from web3 import Web3
from unittest.mock import Mock, patch
import logging
from risk_check import full_risk_assessment
from utils import get_price, calculate_profit
from market_data_aggregator.scripts.fetch_prices import fetch_prices
from market_data_aggregator.scripts.fetch_liquidity import fetch_liquidity

logger = logging.getLogger(__name__)

class Simulator:
    def __init__(self, chain="ethereum"):
        self.chain = chain
        self.results = []
        self.mock_prices = {
            "USDC": 1.0,
            "WETH": 3000.0,
            "DAI": 1.0
        }
    
    @patch('web3.Web3')
    def simulate_trade(self, chain, opportunity, mock_w3):
        """
        Simulate arbitrage trade execution without real RPC.
        Returns dict: {'success': bool, 'pnl': float, 'gas_used': int}
        """
        mock_w3.return_value.eth.estimate_gas.return_value = 500000
        
        # Mock market data
        current_prices = {opp['buy_dex']: self.mock_prices.get(opp['token'], 1.0) * 0.99,
                         opp['sell_dex']: self.mock_prices.get(opp['token'], 1.0) * 1.01}
        liquidity = {opp['token']: 1000000.0}
        
        # Risk check
        safe, risks = full_risk_assessment(opportunity, current_prices, liquidity)
        if not safe:
            return {'success': False, 'reason': risks, 'pnl': 0}
        
        # Simulate execution
        gross_pnl = calculate_profit(current_prices[opportunity['buy_dex']], 
                                   current_prices[opportunity['sell_dex']])
        fees = 0.003 * 2 + 500 / current_prices[opportunity['sell_dex']]  # DEX + gas
        net_pnl = gross_pnl - fees
        
        sim_result = {
            'success': net_pnl > 0,
            'gross_pnl': gross_pnl,
            'net_pnl': net_pnl,
            'slippage': 0.02,  # Simulated
            'gas_used': 500000,
            'risks': risks
        }
        
        self.results.append(sim_result)
        logger.info(f"Sim result: {sim_result}")
        return sim_result
    
    def batch_simulate(self, opportunities):
        """
        Run batch simulation on list of opps.
        """
        results = []
        for opp in opportunities:
            result = self.simulate_trade(self.chain, opp)
            results.append(result)
        return results

def simulate_trade(chain, opportunity):
    """
    Standalone entrypoint.
    """
    sim = Simulator(chain)
    return sim.simulate_trade(chain, opportunity)
