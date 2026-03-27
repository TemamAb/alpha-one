# Real-Time Latency Monitoring for AlphaMark
# Measures and tracks performance metrics across the entire trading pipeline

import time
import logging
import threading
import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from collections import deque
import statistics

logger = logging.getLogger(__name__)


class LatencyMonitor:
    """
    Real-time latency monitoring for the arbitrage engine.
    Tracks:
    - RPC call latency
    - Strategy scan latency
    - Execution latency
    - End-to-end pipeline latency
    """
    
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        
        # Latency tracking for different components
        self.rpc_latencies = deque(maxlen=window_size)
        self.scan_latencies = deque(maxlen=window_size)
        self.execution_latencies = deque(maxlen=window_size)
        self.pipeline_latencies = deque(maxlen=window_size)
        
        # Timestamps for pipeline tracking
        self.pipeline_start = None
        self.scan_complete = None
        self.execution_start = None
        self.execution_complete = None
        
        # Counters
        self.total_opportunities = 0
        self.successful_executions = 0
        self.failed_executions = 0
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Performance targets (in milliseconds)
        self.targets = {
            'rpc_latency': 50,      # 50ms RPC calls
            'scan_latency': 100,    # 100ms full scan
            'execution_latency': 500,  # 500ms to execute
            'pipeline_latency': 1000,  # 1s end-to-end
        }
    
    def start_pipeline_timer(self):
        """Start the end-to-end pipeline timer"""
        with self._lock:
            self.pipeline_start = time.time()
    
    def mark_scan_complete(self):
        """Mark when strategy scan completes"""
        with self._lock:
            if self.pipeline_start:
                scan_time = (time.time() - self.pipeline_start) * 1000
                self.scan_latencies.append(scan_time)
                self.scan_complete = time.time()
    
    def mark_execution_start(self):
        """Mark when execution starts"""
        with self._lock:
            self.execution_start = time.time()
    
    def mark_execution_complete(self, success: bool):
        """Mark when execution completes"""
        with self._lock:
            if self.execution_start:
                exec_time = (time.time() - self.execution_start) * 1000
                self.execution_latencies.append(exec_time)
                self.execution_complete = time.time()
                
                if success:
                    self.successful_executions += 1
                else:
                    self.failed_executions += 1
            
            if self.pipeline_start:
                total_time = (time.time() - self.pipeline_start) * 1000
                self.pipeline_latencies.append(total_time)
                self.total_opportunities += 1
    
    def record_rpc_call(self, latency_ms: float):
        """Record an individual RPC call latency"""
        with self._lock:
            self.rpc_latencies.append(latency_ms)
    
    def get_stats(self) -> Dict:
        """Get current latency statistics"""
        with self._lock:
            return {
                'rpc': self._get_latency_stats(self.rpc_latencies),
                'scan': self._get_latency_stats(self.scan_latencies),
                'execution': self._get_latency_stats(self.execution_latencies),
                'pipeline': self._get_latency_stats(self.pipeline_latencies),
                'success_rate': self._calculate_success_rate(),
                'total_opportunities': self.total_opportunities,
            }
    
    def _get_latency_stats(self, data: deque) -> Dict:
        """Calculate statistics for a latency dataset"""
        if not data:
            return {
                'min': 0,
                'max': 0,
                'avg': 0,
                'p50': 0,
                'p95': 0,
                'p99': 0,
            }
        
        sorted_data = sorted(data)
        n = len(sorted_data)
        
        return {
            'min': round(sorted_data[0], 2),
            'max': round(sorted_data[-1], 2),
            'avg': round(statistics.mean(sorted_data), 2),
            'p50': round(sorted_data[int(n * 0.5)], 2),
            'p95': round(sorted_data[int(n * 0.95)], 2),
            'p99': round(sorted_data[int(n * 0.99)] if n > 1 else sorted_data[0], 2),
        }
    
    def _calculate_success_rate(self) -> float:
        """Calculate execution success rate"""
        total = self.successful_executions + self.failed_executions
        if total == 0:
            return 0.0
        return round(self.successful_executions / total * 100, 2)
    
    def meets_targets(self) -> bool:
        """Check if current performance meets targets"""
        stats = self.get_stats()
        
        # Check average latencies against targets
        if stats['rpc']['avg'] > self.targets['rpc_latency']:
            return False
        if stats['scan']['avg'] > self.targets['scan_latency']:
            return False
        if stats['execution']['avg'] > self.targets['execution_latency']:
            return False
        if stats['pipeline']['avg'] > self.targets['pipeline_latency']:
            return False
        
        return True
    
    def get_performance_report(self) -> str:
        """Generate a performance report"""
        stats = self.get_stats()
        
        report = f"""
╔══════════════════════════════════════════════════════════════╗
║              AlphaMark Performance Report                    ║
╠══════════════════════════════════════════════════════════════╣
║  Total Opportunities: {stats['total_opportunities']:>30}   ║
║  Success Rate:       {stats['success_rate']:>30.1f}%   ║
╠══════════════════════════════════════════════════════════════╣
║  Component    │   Min   │   Avg   │   P95   │  Target    ║
╠══════════════════════════════════════════════════════════════╣
║  RPC          │ {stats['rpc']['min']:>6.1f}ms │ {stats['rpc']['avg']:>6.1f}ms │ {stats['rpc']['p95']:>6.1f}ms │ {self.targets['rpc_latency']:>6.0f}ms   ║
║  Scan         │ {stats['scan']['min']:>6.1f}ms │ {stats['scan']['avg']:>6.1f}ms │ {stats['scan']['p95']:>6.1f}ms │ {self.targets['scan_latency']:>6.0f}ms   ║
║  Execution    │ {stats['execution']['min']:>6.1f}ms │ {stats['execution']['avg']:>6.1f}ms │ {stats['execution']['p95']:>6.1f}ms │ {self.targets['execution_latency']:>6.0f}ms   ║
║  Pipeline     │ {stats['pipeline']['min']:>6.1f}ms │ {stats['pipeline']['avg']:>6.1f}ms │ {stats['pipeline']['p95']:>6.1f}ms │ {self.targets['pipeline_latency']:>6.0f}ms   ║
╚══════════════════════════════════════════════════════════════╝
"""
        return report
    
    def reset(self):
        """Reset all counters"""
        with self._lock:
            self.rpc_latencies.clear()
            self.scan_latencies.clear()
            self.execution_latencies.clear()
            self.pipeline_latencies.clear()
            self.total_opportunities = 0
            self.successful_executions = 0
            self.failed_executions = 0


# Global latency monitor instance
_global_monitor = None
_monitor_lock = threading.Lock()


def get_latency_monitor() -> LatencyMonitor:
    """Get or create the global latency monitor"""
    global _global_monitor
    
    with _monitor_lock:
        if _global_monitor is None:
            _global_monitor = LatencyMonitor()
        return _global_monitor


# Context managers for easy timing
class Timer:
    """Context manager for timing code blocks"""
    
    def __init__(self, monitor: LatencyMonitor, metric_type: str):
        self.monitor = monitor
        self.metric_type = metric_type
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, *args):
        elapsed_ms = (time.time() - self.start_time) * 1000
        
        if self.metric_type == 'rpc':
            self.monitor.record_rpc_call(elapsed_ms)
        elif self.metric_type == 'scan':
            self.monitor.mark_scan_complete()
        elif self.metric_type == 'execution':
            self.monitor.mark_execution_complete(True)


def time_rpc_call(monitor: LatencyMonitor = None):
    """Decorator for timing RPC calls"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            mon = monitor or get_latency_monitor()
            with Timer(mon, 'rpc'):
                result = func(*args, **kwargs)
            return result
        return wrapper
    return decorator


# Example usage in the strategy engine
"""
from monitoring_dashboard.latency_monitor import get_latency_monitor, time_rpc_call

# In strategy.py:
monitor = get_latency_monitor()
monitor.start_pipeline_timer()

# Time an RPC call
with Timer(monitor, 'rpc'):
    price = get_price(chain, dex, token)

# Mark scan complete
monitor.mark_scan_complete()

# In executor.py:
monitor.mark_execution_start()
success, result = execute_flashloan(opportunity)
monitor.mark_execution_complete(success)

# Get stats
stats = monitor.get_stats()
print(stats)
"""
