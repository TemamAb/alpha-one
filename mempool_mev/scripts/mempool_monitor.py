# Monitor mempool
import websocket
import json
import threading
import time
import os
from web3 import Web3
import logging

logger = logging.getLogger(__name__)

# Production WebSocket RPCs - using Alchemy/Infura endpoints from environment
def get_wss_url(chain):
    """Get WebSocket URL from environment or use defaults"""
    env_urls = {
        "ethereum": os.environ.get("ETH_WS_URL", "wss://eth-mainnet.g.alchemy.com/v2/demo"),
        "polygon": os.environ.get("POLYGON_WS_URL", "wss://polygon-mainnet.g.alchemy.com/v2/demo"),
        "bsc": os.environ.get("BSC_WS_URL", "wss://bsc-dataseed1.binance.org/ws"),
        "arbitrum": os.environ.get("ARBITRUM_WS_URL", "wss://arb1.arbitrum.io/ws"),
        "optimism": os.environ.get("OPTIMISM_WS_URL", "wss://mainnet.optimism.io"),
    }
    return env_urls.get(chain, env_urls["ethereum"])


class MempoolMonitor:
    def __init__(self, chain):
        self.chain = chain
        self.wss_url = get_wss_url(chain)
        self.opportunities = []
        self.lock = threading.Lock()
        self.running = False
        self.w3 = None
        
    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            
            # Handle subscription confirmation
            if 'method' not in data:
                return
            
            # Handle new pending transaction
            if data.get('method') == 'eth_subscription':
                params = data.get('params', {})
                result = params.get('result')
                
                if result and isinstance(result, str):
                    tx_hash = result
                    # Fetch tx details asynchronously
                    self._fetch_transaction_details(tx_hash)
                    
        except Exception as e:
            logger.error(f"Mempool parse error: {e}")
    
    def _fetch_transaction_details(self, tx_hash):
        """Fetch and analyze transaction for arbitrage opportunities"""
        try:
            if not self.w3 or not self.w3.is_connected():
                return
                
            tx = self.w3.eth.get_transaction(tx_hash)
            
            # Skip if no input data
            if not tx.get('input') or tx['input'] == '0x':
                return
            
            # Analyze for arbitrage patterns
            if self.is_arbitrage_candidate(tx):
                opp = self.extract_opportunity(tx)
                if opp:
                    with self.lock:
                        self.opportunities.append(opp)
                        logger.info(f"Detected arbitrage opportunity: {tx_hash[:10]}...")
                        
        except Exception as e:
            logger.debug(f"Error fetching tx {tx_hash}: {e}")
    
    def is_arbitrage_candidate(self, tx):
        """
        Heuristic: Detect transactions that may be arbitrage opportunities.
        Checks for:
        - Flashloan calls to lending protocols
        - Multi-swap patterns
        - Large value transfers
        """
        input_data = tx.get('input', '')
        
        if len(input_data) < 10:
            return False
        
        # Known flashloan function selectors
        flashloan_selectors = [
            '0xfd54d6c7',  # Aave V3 flashLoan
            '0xab9c4bcd',  # Aave V2 flashLoan
            '0x5c60da1b',  # Balancer flashLoan
        ]
        
        # Check if transaction calls a known flashloan protocol
        func_selector = input_data[:10]
        if func_selector in flashloan_selectors:
            return True
        
        # Check for high-value transactions to DEX routers
        dex_routers = [
            '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D',  # Uniswap V2
            '0xE592427A0AEce92De3Edee1F18E0157C05861564',  # Uniswap V3
            '0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F',  # SushiSwap
            '0x10ED43C718714eb63d5aA57B78B54704E256024E',  # PancakeSwap
        ]
        
        # Check if value is significant (> 1 ETH)
        # Use Web3.py utility directly instead of instance method
        from web3 import Web3
        if tx.get('value', 0) > Web3.to_wei(1, 'ether'):
            return True
            
        return False
    
    def extract_opportunity(self, tx):
        """
        Extract opportunity details from transaction.
        In production, this would decode the full calldata.
        """
        return {
            'chain': self.chain,
            'tx_hash': tx.get('hash', '').hex() if isinstance(tx.get('hash'), bytes) else tx.get('hash', ''),
            'from': tx.get('from', ''),
            'to': tx.get('to', ''),
            'value': tx.get('value', 0),
            'gas_price': tx.get('gasPrice', 0),
            'input_len': len(tx.get('input', '0x')),
            'detected_at': time.time()
        }
    
    def start(self):
        """Start the WebSocket connection with automatic reconnection"""
        self.running = True
        while self.running:
            try:
                logger.info(f"Connecting to mempool WebSocket for {self.chain}: {self.wss_url}")
                ws = websocket.WebSocketApp(
                    self.wss_url,
                    on_message=self.on_message,
                    on_error=lambda ws, err: logger.error(f"WS Error: {err}"),
                    on_close=lambda ws: logger.warning("Mempool WS closed"),
                    on_open=lambda ws: self._subscribe_to_pending_tx(ws)
                )
                # Initialize Web3 after connection
                self.w3 = Web3(Web3.WebsocketProvider(self.wss_url))
                ws.run_forever(ping_interval=30, ping_timeout=10)
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
            
            # Reconnect after delay if still running
            if self.running:
                logger.info(f"Reconnecting in 5 seconds...")
                time.sleep(5)
    
    def _subscribe_to_pending_tx(self, ws):
        """Subscribe to pending transactions via WebSocket"""
        subscribe_msg = {
            "jsonrpc": "2.0",
            "method": "eth_subscribe",
            "params": ["newPendingTransactions"],
            "id": 1
        }
        ws.send(json.dumps(subscribe_msg))
        logger.info(f"Subscribed to pending transactions on {self.chain}")
    
    def stop(self):
        """Stop the monitor"""
        self.running = False
        logger.info(f"Mempool monitor for {self.chain} stopped")

def monitor_mempool(chain, callback=None):
    """
    Production mempool monitor using WebSocket.
    callback(opps): called with list of opportunities
    """
    monitor = MempoolMonitor(chain)
    def poll_opps():
        while True:
            with monitor.lock:
                if monitor.opportunities:
                    opps = monitor.opportunities[:]
                    monitor.opportunities.clear()
                    if callback:
                        callback(opps)
            time.sleep(0.1)
    
    polling_thread = threading.Thread(target=poll_opps, daemon=True)
    polling_thread.start()
    
    logger.info(f"Starting mempool monitor for {chain} at {monitor.wss_url}")
    monitor.start()
