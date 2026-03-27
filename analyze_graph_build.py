import argparse
import itertools
import json
import os
import sys
from collections import defaultdict


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
STRATEGY_SRC = os.path.join(PROJECT_ROOT, "strategy_engine", "src")
sys.path.insert(0, STRATEGY_SRC)

from web3 import Web3

import utils


CONFIG_PATH = os.path.join(PROJECT_ROOT, "config_asset_registry", "data", "contracts.json")
IGNORE_KEYS = {"testnet", "paper_trading"}


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def to_checksum_map(tokens):
    checksummed = {}
    for symbol, address in (tokens or {}).items():
        try:
            checksummed[symbol] = Web3.to_checksum_address(address)
        except Exception:
            continue
    return checksummed


def build_static_graph(chain_data):
    tokens = to_checksum_map(chain_data.get("tokens", {}))
    dexes = chain_data.get("dexes", {})
    graph = defaultdict(set)
    dex_routers = defaultdict(set)

    token_items = list(tokens.items())
    for _, addr_a in token_items:
        for _, addr_b in token_items:
            if addr_a == addr_b:
                continue
            graph[addr_a].add(addr_b)

    for _, addr_a in token_items:
        for _, addr_b in token_items:
            if addr_a >= addr_b:
                continue
            pair = tuple(sorted((addr_a, addr_b)))
            for _, router in dexes.items():
                dex_routers[pair].add(Web3.to_checksum_address(router))

    return tokens, graph, dex_routers


def undirected_edge_count(graph):
    edges = set()
    for source, neighbors in graph.items():
        for target in neighbors:
            edges.add(tuple(sorted((source, target))))
    return len(edges)


def count_cycles(graph, base_token, max_hops=3):
    cycles = set()

    def dfs(path, visited, depth):
        if depth >= 2 and base_token in graph.get(path[-1], set()):
            cycles.add(tuple(path + [base_token]))
        if depth >= max_hops:
            return
        for neighbor in graph.get(path[-1], set()):
            if neighbor not in visited:
                dfs(path + [neighbor], visited | {neighbor}, depth + 1)

    dfs([base_token], {base_token}, 1)
    return len(cycles)


def base_token_for_chain(chain_data, tokens):
    return (
        tokens.get("WETH")
        or tokens.get("WMATIC")
        or tokens.get("WBNB")
        or tokens.get("WAVAX")
        or (Web3.to_checksum_address(chain_data["weth_address"]) if chain_data.get("weth_address") else None)
    )


def summarize_static(chain_name, chain_data):
    tokens, graph, dex_routers = build_static_graph(chain_data)
    base_token = base_token_for_chain(chain_data, tokens)
    max_pairs_per_dex = len(tokens) * (len(tokens) - 1) // 2
    routed_pair_edges = sum(len(routers) for routers in dex_routers.values())
    cycle_count = count_cycles(graph, base_token) if base_token else 0

    return {
        "chain": chain_name,
        "token_count": len(tokens),
        "dex_count": len(chain_data.get("dexes", {})),
        "unique_pairs": undirected_edge_count(graph),
        "router_pair_edges": routed_pair_edges,
        "max_pairs_per_dex": max_pairs_per_dex,
        "cycle_count_up_to_3_hops": cycle_count,
        "base_token": base_token,
    }


def summarize_onchain(chain_name, chain_data):
    rpc = utils.get_rpc(chain_name)
    if not rpc:
        return {"chain": chain_name, "onchain_error": "no_reachable_rpc"}

    w3 = Web3(Web3.HTTPProvider(rpc, session=utils.get_w3_session()))
    merged_graph = defaultdict(set)
    merged_edges = defaultdict(set)

    for dex_name, factory_address in chain_data.get("factories", {}).items():
        router = chain_data.get("dexes", {}).get(dex_name)
        if not router:
            continue
        dex_graph = utils.get_all_dex_pairs(w3, factory_address, chain_name=chain_name)
        for source, neighbors in dex_graph.items():
            merged_graph[source].update(neighbors)
            for target in neighbors:
                merged_edges[tuple(sorted((source, target)))].add(Web3.to_checksum_address(router))

    tokens = to_checksum_map(chain_data.get("tokens", {}))
    base_token = base_token_for_chain(chain_data, tokens)
    cycle_count = count_cycles(merged_graph, base_token) if base_token else 0

    return {
        "chain": chain_name,
        "onchain_tokens": len(merged_graph),
        "onchain_unique_pairs": undirected_edge_count(merged_graph),
        "onchain_router_pair_edges": sum(len(routers) for routers in merged_edges.values()),
        "onchain_cycle_count_up_to_3_hops": cycle_count,
        "rpc": rpc,
    }


def main():
    parser = argparse.ArgumentParser(description="Analyze AlphaMark graph-building coverage.")
    parser.add_argument("--chain", help="Analyze a single chain from contracts.json")
    parser.add_argument("--onchain", action="store_true", help="Attempt on-chain factory graph analysis via reachable RPCs")
    args = parser.parse_args()

    config = load_config()
    chain_names = [args.chain] if args.chain else [name for name in config.keys() if name not in IGNORE_KEYS]

    results = []
    for chain_name in chain_names:
        chain_data = config.get(chain_name)
        if not isinstance(chain_data, dict):
            continue

        static_summary = summarize_static(chain_name, chain_data)
        if args.onchain:
            static_summary["onchain"] = summarize_onchain(chain_name, chain_data)
        results.append(static_summary)

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
