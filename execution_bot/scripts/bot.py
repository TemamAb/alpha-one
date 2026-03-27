# Bot loop
import time
import logging
import threading
import os
import requests
from datetime import datetime
import sys
import multiprocessing
import json
import csv
from dotenv import load_dotenv

# Initialize Logger early to prevent NameError in fallbacks
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Get the project root directory
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Fix: Set CWD to project root so relative config paths in strategy/utils work inside Docker
os.chdir(PROJECT_ROOT)

# Load environment variables from .env file
load_dotenv()

sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "strategy_engine", "src"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "market_data_aggregator", "scripts"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import redis

from utils import estimate_net_profit
from risk_management.risk_check import full_risk_assessment

try:
    from alerts import send_alert
except ImportError:
    # Fallback if alerts.py is missing/not found
    def send_alert(msg): logging.info(f"ALERT: {msg}")

# Import the module object to modify global state dynamically
import executor
# ARCHITECT FIX: Force mode synchronization from environment immediately on import to ensure safety
executor.PAPER_TRADING_MODE = os.environ.get("PAPER_TRADING_MODE", "true").lower() == "true"
from executor import execute_flashloan

try:
    from fetch_liquidity import fetch_liquidity
except ImportError:
    def fetch_liquidity(chain, token): 
        logger.error(f"MISSING LIQUIDITY DATA for {token} on {chain}. Returning 0 to prevent false arb signals.")
        return 0.0

# Implement structured logging
import json
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "worker_id": getattr(record, 'worker_id', 'MAIN'),  # Default to MAIN if no worker_id
            "message": record.getMessage(),
            "chain": getattr(record, 'chain', 'SYSTEM'),  # Default to SYSTEM for global logs
        }
        return json.dumps(log_record)

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
if not root_logger.handlers:
    logHandler = logging.StreamHandler()
    logHandler.setFormatter(JsonFormatter())
    root_logger.addHandler(logHandler)

# --- Self-Learning System ---
LEARNING_DATA_FILE = 'trade_history.csv'

def initialize_learning_system():
    if not os.path.exists(LEARNING_DATA_FILE):
        with open(LEARNING_DATA_FILE, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'chain', 'strategy', 'profit_usd', 'loan_amount',
                'path', 'gas_price', 'volatility_metric', 'model_confidence',
                'risk_assessment_passed', 'execution_success', 'net_profit_eth'
            ])

def learn_from_trade(opportunity, success, net_profit, model_confidence, risk_passed):
    try:
        with open(LEARNING_DATA_FILE, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(),
                opportunity.get('chain'),
                opportunity.get('strategy'),
                opportunity.get('net_usd_profit'),
                opportunity.get('loan_amount'),
                "->".join(opportunity.get('path', [])),
                opportunity.get('gas_price', 0),
                0.5,
                model_confidence,
                risk_passed,
                success,
                net_profit if success else 0
            ])
    except Exception as e:
        logger.error(f"Failed to record learning data: {e}")

def get_model_confidence(opportunity):
    return 0.75 + (len(opportunity.get('path', [])) * 0.05)

# Configuration
REDIS_URL = os.environ.get("REDIS_URL")
_internal_host = os.getenv("DASHBOARD_HOSTPORT")
DASHBOARD_URL = os.getenv("DASHBOARD_URL")

# ARCHITECT FIX: Check Redis for dynamic DASHBOARD_URL override (Priority)
if REDIS_URL:
    try:
        r_temp = redis.from_url(REDIS_URL, socket_timeout=1, decode_responses=True)
        redis_url_override = r_temp.hget("alphamark:env", "DASHBOARD_URL")
        if redis_url_override:
            DASHBOARD_URL = redis_url_override
            logger.info(f"Using dynamic DASHBOARD_URL from Redis: {DASHBOARD_URL}")
    except: pass

if not DASHBOARD_URL:
    DASHBOARD_URL = f"http://{_internal_host}" if _internal_host else "http://localhost:3000"
ACTIVE_WALLETS = {}
MAX_SLIPPAGE = float(os.getenv("MAX_SLIPPAGE", "0.005"))
MIN_LIQUIDITY = int(os.getenv("MIN_LIQUIDITY", "1000"))

def report_execution_to_dashboard(opportunity, success, profit=0, loss=0, tx_hash=None):
    def _send():
        try:
            payload = {
                "success": success,
                "profit": profit,
                "loss": loss,
                "chain": opportunity.get('chain'),
                "txHash": tx_hash,
                "timestamp": datetime.now().isoformat()
            }
            requests.post(f"{DASHBOARD_URL}/api/bot/update", json=payload, timeout=2)
        except: pass
    threading.Thread(target=_send, daemon=True).start()

def report_heartbeat(active_opps_count):
    def _send():
        try:
            payload = {"type": "HEARTBEAT", "activeOpps": active_opps_count, "timestamp": datetime.now().isoformat()}
            requests.post(f"{DASHBOARD_URL}/api/bot/update", json=payload, timeout=2)
        except: pass
    threading.Thread(target=_send, daemon=True).start()

# --- OPTIMIZED DYNAMIC PROCESSES ---

# Services moved to alpha_engine.py to prevent circular imports

def control_listener():
    global ACTIVE_WALLETS
    if not REDIS_URL: return
    try:
        r = redis.from_url(REDIS_URL, socket_timeout=2, decode_responses=True)
        ps = r.pubsub()
        ps.subscribe('alphamark:control', 'alphamark:config')
        for msg in ps.listen():
            if msg['type'] == 'message':
                data = json.loads(msg['data'])
                if data.get('command') == 'START':
                    r.set('alphamark:mode', data.get('mode', 'paper'))
                    r.set('alphamark:status', 'RUNNING')
                    os.environ["PAPER_TRADING_MODE"] = 'true' if data.get('mode', 'paper') == 'paper' else 'false'
                    executor.PAPER_TRADING_MODE = os.environ["PAPER_TRADING_MODE"] == 'true'
                elif data.get('command') == 'PAUSE':
                    r.set('alphamark:status', 'PAUSED')
                elif data.get('command') == 'STOP':
                    r.set('alphamark:status', 'STOPPED')
                elif data.get('type') == 'WALLET_ADD':
                    wallet_data = data.get('data', {})
                    if wallet_data.get('address') and wallet_data.get('privateKey'):
                        r.set(f"alphamark:wallet:{wallet_data['address']}:private_key", wallet_data['privateKey'])
                        r.set('alphamark:active_wallet_address', wallet_data['address'])
                elif data.get('type') == 'WALLET_REMOVE':
                    wallet_data = data.get('data', {})
                    if wallet_data.get('address'):
                        r.delete(f"alphamark:wallet:{wallet_data['address']}:private_key")
                elif data.get('type') == 'ENV_UPDATE':
                    # Configuration dynamic reload
                    env_data = data.get('data', {})
                    for k, v in env_data.items():
                        os.environ[k] = str(v)
                    
                    if "PAPER_TRADING_MODE" in env_data:
                        val = str(env_data["PAPER_TRADING_MODE"]).lower() == "true"
                        executor.PAPER_TRADING_MODE = val
                    
                    # Force a refresh of all dependent components (RPCs, keys etc)
                    executor.sync_runtime_state()
                    logger.info(f"Engine: Configuration reloaded at runtime ({len(env_data)} keys updated).")

                elif data.get('type') == 'WALLET_UPDATE':
                    wallet_data = data.get('data', {})
                    if wallet_data.get('address'):
                        r.set('alphamark:active_wallet_address', wallet_data['address'])
                        executor.sync_runtime_state()
    except: pass

def wallet_balance_updater():
    if not REDIS_URL: return
    while True:
        # Simple simulated balance updater for now
        time.sleep(60)

# --- ORCHESTRATOR INTEGRATION ---
from orchestrator import AlphaOrchestrator

def run_bot():
    """
    Main function to orchestrate the multi-process bot via AlphaOrchestrator.
    """
    logger.info("🚀 Starting Alphamark ENTERPRISE ORCHESTRATOR...")
    initialize_learning_system()
    
    try:
        multiprocessing.set_start_method('spawn', force=True)
    except RuntimeError: pass

    from strategy import CONFIG
    opportunity_queue = multiprocessing.Queue()
    
    # Start background control threads
    threading.Thread(target=control_listener, daemon=True).start()
    # threading.Thread(target=wallet_balance_updater, daemon=True).start()

    # Initialise the Chief Orchestrator
    orchestrator = AlphaOrchestrator(
        opportunity_queue=opportunity_queue, 
        redis_url=REDIS_URL,
        dashboard_url=DASHBOARD_URL
    )
    
    # Scan for chains and deploy dedicated processes
    orchestrator.initialize_chains(CONFIG)
    orchestrator.start() # This is blocking and manages the loop

if __name__ == "__main__":
    run_bot()
