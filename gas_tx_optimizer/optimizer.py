# Gas & transaction optimizer
from web3 import Web3
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class GasOptimizer:
    def __init__(self):
        self.cache = {}  # method_id -> avg_gas
    
    def estimate_gas(self, w3: Web3, contract_address: str, function_name: str, params: list, value=0) -> int:
        """
        Estimate gas for specific contract call.
        Caches results for speed.
        """
        # Build method signature for keccak
        param_types = ','.join([str(p.type) for p in params]) if params else ''
        method_signature = f"{function_name}({param_types})"
        method_id = w3.keccak(text=method_signature)[:4].hex()
        key = f"{contract_address}:{method_id}"
        
        if key in self.cache:
            return self.cache[key]
        
        try:
            # Build call_data
            call_data = w3.eth.abi.encode_function_call(
                self.get_abi(function_name), params
            )
            
            gas_estimate = w3.eth.estimate_gas({
                'to': contract_address,
                'data': call_data,
                'value': value,
                'from': w3.eth.default_account
            })
            
            self.cache[key] = int(gas_estimate * 1.2)  # 20% buffer
            return self.cache[key]
            
        except Exception as e:
            logger.warning(f"Gas estimate failed: {e}, using fallback")
            return 1000000  # Safe fallback
    
    def optimize_bundle(self, txs: list) -> list:
        """
        Optimize tx bundle gas: order by gas price, compress calldata.
        """
        # Sort by urgency (high profit first)
        optimized = sorted(txs, key=lambda tx: tx.get('profit', 0), reverse=True)
        
        total_gas = sum(self.estimate_gas(**tx['w3'], **tx['call']) for tx in optimized)
        logger.info(f"Bundle optimized: {len(optimized)} txs, {total_gas} gas")
        return optimized
    
    def get_optimal_gas_price(self, w3: Web3, percentile=75) -> Dict[str, int]:
        """
        Get dynamic gas price from mempool.
        Uses pending transactions pool for accurate gas pricing.
        """
        # Default values in case of failure
        default_fee = w3.to_wei('30', 'gwei')
        priority_fee = w3.to_wei('2', 'gwei')
        
        try:
            # FIXED: max_priority_fee is a method, not a property - call it with ()
            priority_fee = w3.eth.max_priority_fee()
            
            # Get pending transactions from the pool
            # Filter by transactions with reasonable gas prices
            pending_transactions = w3.eth.get_block('pending', full_transactions=True)
            if pending_transactions and pending_transactions.transactions:
                # Get gas prices from pending transactions
                gas_prices = []
                for tx in pending_transactions.transactions:
                    if isinstance(tx, dict) and 'maxFeePerGas' in tx:
                        gas_prices.append(tx['maxFeePerGas'])
                
                if gas_prices:
                    sorted_prices = sorted(gas_prices)
                    idx = int(len(sorted_prices) * percentile / 100)
                    idx = min(idx, len(sorted_prices) - 1)
                    optimal = sorted_prices[idx]
                else:
                    optimal = default_fee
            else:
                # Fallback: estimate based on recent blocks
                latest_block = w3.eth.get_block('latest')
                if 'baseFeePerGas' in latest_block:
                    # EIP-1559: use baseFeePerGas + priority fee
                    optimal = latest_block['baseFeePerGas'] + priority_fee
                else:
                    optimal = default_fee
        except Exception as e:
            logger.warning(f"Gas price estimation failed: {e}, using fallback")
            optimal = default_fee
        
        return {
            'maxFeePerGas': optimal,
            'maxPriorityFeePerGas': priority_fee,
            'gasLimit': 1500000  # Bundle safe
        }

def estimate_gas(chain, tx_data):
    """
    Legacy entrypoint for gas estimation.
    """
    optimizer = GasOptimizer()
    w3 = Web3(Web3.HTTPProvider(tx_data['rpc']))
    return optimizer.estimate_gas(w3, tx_data['to'], tx_data['function'], tx_data['params'])
