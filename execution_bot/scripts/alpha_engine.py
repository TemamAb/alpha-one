import time
import logging
import os
import sys
import multiprocessing
import redis
from datetime import datetime
import requests
import threading
import json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "strategy_engine", "src"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "market_data_aggregator", "scripts"))
from fetch_liquidity import fetch_liquidity
import utils

logger = logging.getLogger("alpha.engine")

REDIS_URL = os.environ.get("REDIS_URL")
DASHBOARD_HOSTPORT = os.getenv("DASHBOARD_HOSTPORT")
DASHBOARD_URL = os.getenv("DASHBOARD_URL") or (f"http://{DASHBOARD_HOSTPORT}" if DASHBOARD_HOSTPORT else "http://localhost:3000")
MAX_SLIPPAGE = float(os.getenv("MAX_SLIPPAGE", "0.005"))
MIN_LIQUIDITY = int(os.getenv("MIN_LIQUIDITY", "1000"))

PERF_STATE = {
    "scanLatencyMs": 0.0,
    "scanLatencyMeasured": False,
    "executionLatencyMs": 0.0,
    "executionLatencyMeasured": False,
    "rpcLatencyMs": 0.0,
    "rpcLatencyMeasured": False,
    "opportunitiesRejected": 0,
    "opportunitiesFound": 0,
    "successfulExecutions": 0,
    "failedExecutions": 0,
}

SCAN_DIAGNOSTICS_KEY = "alphamark:scan_diagnostics"
PERF_METRICS_KEY = "alphamark:perf_metrics"


def _update_avg(metric_name, value):
    previous = PERF_STATE.get(metric_name, 0.0)
    PERF_STATE[metric_name] = value if previous == 0 else ((previous * 0.7) + (value * 0.3))


def build_performance_metrics(opportunity_queue=None):
    queue_depth = 0
    if opportunity_queue is not None:
        try:
            queue_depth = opportunity_queue.qsize()
        except Exception:
            queue_depth = 0
    rpc_snapshot = utils.get_rpc_latency_snapshot()
    rpc_avg = (sum(rpc_snapshot.values()) / len(rpc_snapshot)) if rpc_snapshot else 0.0
    shared_perf = get_shared_perf_snapshot()
    scan_diagnostics = get_scan_diagnostics_snapshot()
    scan_latency_samples = shared_perf.get("scanLatencySamples", 0.0)
    execution_latency_samples = shared_perf.get("executionLatencySamples", 0.0)
    scan_latency_ms = (
        shared_perf.get("scanLatencyTotalMs", 0.0) / scan_latency_samples
        if scan_latency_samples else PERF_STATE["scanLatencyMs"]
    )
    execution_latency_ms = (
        shared_perf.get("executionLatencyTotalMs", 0.0) / execution_latency_samples
        if execution_latency_samples else PERF_STATE["executionLatencyMs"]
    )
    return {
        "latencyMs": round(execution_latency_ms or scan_latency_ms or 0.0, 2),
        "latencyMeasured": bool(execution_latency_samples or scan_latency_samples),
        "scanLatencyMs": round(scan_latency_ms, 2),
        "scanLatencyMeasured": bool(scan_latency_samples),
        "executionLatencyMs": round(execution_latency_ms, 2),
        "executionLatencyMeasured": bool(execution_latency_samples),
        "rpcLatencyMs": round(rpc_avg, 2),
        "rpcLatencyMeasured": bool(rpc_snapshot),
        "rpcLatencyByChain": rpc_snapshot,
        "scanDiagnostics": scan_diagnostics,
        "opportunitiesRejected": int(shared_perf.get("opportunitiesRejected", PERF_STATE["opportunitiesRejected"])),
        "opportunitiesFound": int(shared_perf.get("opportunitiesFound", PERF_STATE["opportunitiesFound"])),
        "successfulExecutions": int(shared_perf.get("successfulExecutions", PERF_STATE["successfulExecutions"])),
        "failedExecutions": int(shared_perf.get("failedExecutions", PERF_STATE["failedExecutions"])),
        "queueDepth": queue_depth
    }


def persist_scan_diagnostics(chain_name, diagnostics, redis_client=None):
    if not chain_name or not diagnostics or not redis_client:
        return
    try:
        redis_client.hset(SCAN_DIAGNOSTICS_KEY, chain_name, json.dumps(diagnostics))
        redis_client.expire(SCAN_DIAGNOSTICS_KEY, 300)
    except Exception:
        pass


def persist_perf_sample(metric_name, value, redis_client=None):
    if redis_client is None:
        return
    sample_field_map = {
        "scanLatencyMs": ("scanLatencyTotalMs", "scanLatencySamples"),
        "executionLatencyMs": ("executionLatencyTotalMs", "executionLatencySamples"),
    }
    total_field, count_field = sample_field_map.get(metric_name, (None, None))
    if not total_field:
        return
    try:
        redis_client.hincrbyfloat(PERF_METRICS_KEY, total_field, float(value))
        redis_client.hincrby(PERF_METRICS_KEY, count_field, 1)
        redis_client.expire(PERF_METRICS_KEY, 300)
    except Exception:
        pass


def increment_perf_counter(metric_name, amount=1, redis_client=None):
    if redis_client is None:
        return
    try:
        redis_client.hincrby(PERF_METRICS_KEY, metric_name, int(amount))
        redis_client.expire(PERF_METRICS_KEY, 300)
    except Exception:
        pass


def get_shared_perf_snapshot(redis_client=None):
    client = redis_client
    if client is None and REDIS_URL:
        try:
            client = redis.from_url(REDIS_URL, socket_timeout=1, socket_connect_timeout=1)
            client.ping()
        except Exception:
            client = None

    if client:
        try:
            raw_values = client.hgetall(PERF_METRICS_KEY)
            if raw_values:
                snapshot = {}
                for key, value in raw_values.items():
                    metric_name = key.decode() if isinstance(key, bytes) else str(key)
                    raw_value = value.decode() if isinstance(value, bytes) else value
                    try:
                        snapshot[metric_name] = float(raw_value)
                    except (TypeError, ValueError):
                        continue
                return snapshot
        except Exception:
            pass
    return {}


def get_scan_diagnostics_snapshot(redis_client=None):
    client = redis_client
    if client is None and REDIS_URL:
        try:
            client = redis.from_url(REDIS_URL, socket_timeout=1, socket_connect_timeout=1)
            client.ping()
        except Exception:
            client = None

    if client:
        try:
            raw_values = client.hgetall(SCAN_DIAGNOSTICS_KEY)
            if raw_values:
                diagnostics = {}
                for chain_name, payload in raw_values.items():
                    key = chain_name.decode() if isinstance(chain_name, bytes) else str(chain_name)
                    body = payload.decode() if isinstance(payload, bytes) else payload
                    try:
                        diagnostics[key] = json.loads(body)
                    except (TypeError, ValueError):
                        continue
                return diagnostics
        except Exception:
            pass
    return {}


def get_runtime_control_state(redis_client=None):
    status = "STOPPED"
    mode = "paper" if os.environ.get("PAPER_TRADING_MODE", "true").lower() == "true" else "live"

    if redis_client:
        try:
            raw_status = redis_client.get("alphamark:status")
            raw_mode = redis_client.get("alphamark:mode")
            if raw_status:
                status = raw_status.decode() if isinstance(raw_status, bytes) else raw_status
            if raw_mode:
                mode = raw_mode.decode() if isinstance(raw_mode, bytes) else raw_mode
        except Exception:
            pass

    return status, mode


def report_heartbeat(active_opps_count, performance_metrics=None):
    try:
        payload = {
            "type": "HEARTBEAT",
            "activeOpps": active_opps_count,
            "timestamp": datetime.now().isoformat(),
            "performanceMetrics": performance_metrics or build_performance_metrics()
        }
        requests.post(f"{DASHBOARD_URL}/api/bot/update", json=payload, timeout=2)
    except Exception:
        pass


def get_model_confidence(opportunity):
    return 0.75 + (len(opportunity.get("path", [])) * 0.05)


def report_execution_to_dashboard(opportunity, success, profit=0, loss=0, tx_hash=None, performance_metrics=None):
    try:
        chain = opportunity.get("chain", "NETWORK")
        payload = {
            "success": success,
            "profit": profit,
            "loss": loss,
            "chain": chain,
            "txHash": tx_hash or "N/A",
            "timestamp": datetime.now().isoformat(),
            "performanceMetrics": performance_metrics or build_performance_metrics()
        }
        requests.post(f"{DASHBOARD_URL}/api/bot/update", json=payload, timeout=2)
    except Exception as e:
        logger.debug(f"Dashboard report failed: {e}")


def chain_scanner(opportunity_queue: multiprocessing.Queue, target_chain: str = None):
    """
    Enterprise-grade chain scanner.
    Targets a specific blockchain or executes a global market scan.
    """
    from strategy import find_graph_arbitrage_opportunities, find_profitable_opportunities, CONFIG

    logger.info(f"Scanner Service initialized for {target_chain or 'ALL NETWORKS'}", extra={"chain": target_chain or "SYSTEM"})

    redis_client = None
    if REDIS_URL:
        try:
            redis_client = redis.from_url(REDIS_URL, socket_timeout=2)
            redis_client.ping()
        except Exception:
            pass

    scanner_state = {"active_opps": 0}

    def heartbeat_loop():
        while True:
            report_heartbeat(scanner_state["active_opps"], build_performance_metrics(opportunity_queue))
            time.sleep(5)

    threading.Thread(target=heartbeat_loop, daemon=True).start()

    while True:
        if os.environ.get("KILL_SWITCH") == "true":
            return

        if redis_client:
            try:
                kill_switch = redis_client.get("alphamark:kill_switch")
                if kill_switch and kill_switch.decode() == "true":
                    return
            except Exception:
                pass

        try:
            status, _ = get_runtime_control_state(redis_client)
            if status == "PAUSED":
                report_heartbeat(0, build_performance_metrics(opportunity_queue))
                time.sleep(1)
                continue
            if status == "STOPPED":
                report_heartbeat(0, build_performance_metrics(opportunity_queue))
                time.sleep(1)
                continue

            scan_started = time.time()
            if target_chain and target_chain in CONFIG:
                opps, diagnostics = find_graph_arbitrage_opportunities(
                    target_chain,
                    CONFIG[target_chain],
                    return_diagnostics=True
                )
                persist_scan_diagnostics(target_chain, diagnostics, redis_client)
            else:
                opps = find_profitable_opportunities()

            _update_avg("scanLatencyMs", (time.time() - scan_started) * 1000)
            PERF_STATE["scanLatencyMeasured"] = True
            persist_perf_sample("scanLatencyMs", (time.time() - scan_started) * 1000, redis_client)

            scanner_state["active_opps"] = len(opps) if opps else 0
            PERF_STATE["opportunitiesFound"] += len(opps) if opps else 0
            if opps:
                increment_perf_counter("opportunitiesFound", len(opps), redis_client)

            if opps:
                logger.info(
                    f"Scanner [{target_chain or 'MASTER'}] identified {len(opps)} opportunities.",
                    extra={"chain": target_chain or "SYSTEM"},
                )
                for opportunity in opps:
                    opportunity_queue.put(opportunity)

            report_heartbeat(scanner_state["active_opps"], build_performance_metrics(opportunity_queue))
            time.sleep(0.3)
        except Exception as e:
            scanner_state["active_opps"] = 0
            report_heartbeat(0, build_performance_metrics(opportunity_queue))
            logger.error(f"Scanner service error: {e}")
            time.sleep(5)


def execution_service(opportunity_queue: multiprocessing.Queue, service_id: int):
    """
    High-frequency execution service.
    Pulls signals from the orchestrator and executes transactions on-chain.
    """
    import executor
    from executor import execute_flashloan
    from risk_management.risk_check import full_risk_assessment

    exec_logger = logging.getLogger(f"execution.service.{service_id}")
    exec_logger.setLevel(logging.INFO)
    exec_logger.info(f"Execution Service #{service_id}: READY.")

    redis_client = None
    if REDIS_URL:
        try:
            redis_client = redis.from_url(REDIS_URL, socket_timeout=2)
            redis_client.ping()
        except Exception:
            redis_client = None

    while True:
        try:
            status, mode = get_runtime_control_state(redis_client)
            if status == "PAUSED":
                time.sleep(1)
                continue
            if status == "STOPPED":
                time.sleep(1)
                continue

            executor.PAPER_TRADING_MODE = mode != "live"
            opportunity = opportunity_queue.get()

            if opportunity.get("strategy") == "monitor_only":
                exec_logger.debug(f"Service #{service_id} skipped monitor-only signal for {opportunity.get('chain')}")
                continue

            exec_logger.info(f"Service #{service_id} executing signal for {opportunity.get('chain', 'NETWORK')}")

            model_confidence = get_model_confidence(opportunity)
            current_prices = {
                "buy_dex": opportunity.get("buy_price", "dex"),
                "sell_dex": opportunity.get("sell_price", "dex")
            }
            pool_liquidity = fetch_liquidity(opportunity["chain"], opportunity.get("token", "WETH"))
            liquidity_data = {opportunity.get("token", "WETH"): pool_liquidity}

            safe, risks = full_risk_assessment(
                opportunity,
                current_prices,
                liquidity_data,
                model_confidence,
                MAX_SLIPPAGE,
                MIN_LIQUIDITY,
            )
            if not safe:
                PERF_STATE["opportunitiesRejected"] += 1
                increment_perf_counter("opportunitiesRejected", 1, redis_client)
                exec_logger.warning(f"Service #{service_id} rejected risky trade: {risks}")
                continue

            execution_started = time.time()
            success, tx_hash = execute_flashloan(opportunity)
            _update_avg("executionLatencyMs", (time.time() - execution_started) * 1000)
            PERF_STATE["executionLatencyMeasured"] = True
            persist_perf_sample("executionLatencyMs", (time.time() - execution_started) * 1000, redis_client)

            if success:
                PERF_STATE["successfulExecutions"] += 1
                increment_perf_counter("successfulExecutions", 1, redis_client)
                logger.info(f"EXECUTION SUCCESS on {opportunity['chain']}! Hash: {tx_hash}", extra={"chain": opportunity["chain"]})
                report_execution_to_dashboard(
                    opportunity,
                    True,
                    profit=opportunity.get("profit_eth", 0),
                    tx_hash=tx_hash,
                    performance_metrics=build_performance_metrics(opportunity_queue),
                )
            else:
                PERF_STATE["failedExecutions"] += 1
                increment_perf_counter("failedExecutions", 1, redis_client)
                report_execution_to_dashboard(
                    opportunity,
                    False,
                    tx_hash=tx_hash,
                    performance_metrics=build_performance_metrics(opportunity_queue),
                )

        except Exception as e:
            exec_logger.error(f"Execution Service error: {e}")
