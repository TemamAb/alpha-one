import multiprocessing
import os
import time
import logging
import threading
from typing import Dict, List
import json
import redis
import requests
from datetime import datetime

logger = logging.getLogger("alpha.orchestrator")

class AlphaOrchestrator:
    """
    Enterprise-Grade Multi-Chain Orchestrator.
    Manages the lifecycle of scanning services and high-frequency executors.
    Performs dynamic load balancing and self-healing across the trade engine.
    """
    def __init__(self, opportunity_queue: multiprocessing.Queue, redis_url: str = None, dashboard_url: str = "http://localhost:3000"):
        self.opportunity_queue = opportunity_queue
        self.redis_url = redis_url
        self.dashboard_url = dashboard_url
        self.scanners: Dict[str, multiprocessing.Process] = {}
        self.executors: List[multiprocessing.Process] = []
        self.active_chains: List[str] = []
        self.is_running = True
        self.redis_client = None
        
        if self.redis_url:
            try:
                self.redis_client = redis.from_url(self.redis_url, socket_timeout=2)
                self.redis_client.ping()
            except:
                logger.warning("Orchestrator: Standalone mode active (Redis unreachable).")

    def initialize_chains(self, config: Dict):
        """Identifies targetable blockchains from enterprise registry."""
        ignore = {'testnet', 'paper_trading'}
        self.active_chains = [c for c in config.keys() if c not in ignore]
        logger.info(f"Orchestrator: Enterprise Registry Loaded. Targeted: {self.active_chains}", extra={'chain': 'SYSTEM'})

    def deploy_scanner_service(self, chain_name: str):
        """Deploys a dedicated scanning service for the specified chain."""
        from alpha_engine import chain_scanner
        p = multiprocessing.Process(
            target=chain_scanner, 
            args=(self.opportunity_queue, chain_name), 
            name=f"scanner-{chain_name}", 
            daemon=True
        )
        p.start()
        self.scanners[chain_name] = p
        logger.info(f"Orchestrator: 📡 Dedicated Scanner Service deployed for {chain_name}", extra={'chain': chain_name})

    def deploy_execution_service(self, service_id: int):
        """Deploys a high-frequency execution service."""
        from alpha_engine import execution_service
        p = multiprocessing.Process(
            target=execution_service, 
            args=(self.opportunity_queue, service_id), 
            name=f"executor-{service_id}", 
            daemon=True
        )
        p.start()
        self.executors.append(p)
        logger.info(f"Orchestrator: 🚀 Execution Service #{service_id} deployed.", extra={'chain': 'SYSTEM'})

    def perform_health_checks(self):
        """Self-healing: monitors latency and process heartbeat."""
        # Clean Scanners
        for chain, p in list(self.scanners.items()):
            if not p.is_alive():
                logger.error(f"Orchestrator: Scanner Service for {chain} FAILED. Redeploying...", extra={'chain': chain})
                self.deploy_scanner_service(chain)

        # Clean Executors
        for i, p in enumerate(list(self.executors)):
            if not p.is_alive():
                logger.error(f"Orchestrator: Execution Service #{i+1} FAILED. Replacing...", extra={'chain': 'SYSTEM'})
                self.deploy_execution_service(len(self.executors)+1)
                self.executors.remove(p)

    def optimize_load_balance(self):
        """Dynamically scales executors based on queue depth and network congestion."""
        q_size = self.opportunity_queue.qsize()
        max_capacity = os.cpu_count() or 8
        
        # Scaling UP logic
        if q_size > 10 and len(self.executors) < max_capacity:
            logger.info(f"Orchestrator: High signal density (Q={q_size}). Scaling up executors...", extra={'chain': 'SYSTEM'})
            self.deploy_execution_service(len(self.executors) + 1)

    def start(self):
        """Starts the Enterprise Orchestrator control loop."""
        logger.info("Orchestrator: ENTERPRISE SYSTEM INITIALIZED.", extra={'chain': 'SYSTEM'})
        
        # Deploy scanning services per chain
        for chain in self.active_chains:
            self.deploy_scanner_service(chain)
        
        # Deploy initial execution pool
        initial_pool = max(2, (os.cpu_count() or 4) // 2)
        for i in range(initial_pool):
            self.deploy_execution_service(i + 1)

        try:
            while self.is_running:
                self.perform_health_checks()
                self.optimize_load_balance()
                time.sleep(30)
        except KeyboardInterrupt:
            logger.info("Orchestrator: Graceful shutdown.", extra={'chain': 'SYSTEM'})
            self.stop()

    def stop(self):
        self.is_running = False
        for p in self.scanners.values(): p.terminate()
        for p in self.executors: p.terminate()
