# The Graph Integration for AlphaMark
# Provides fast subgraph queries for DEX pair discovery

import requests
import logging
from typing import Dict, List, Optional, Any
from web3 import Web3

logger = logging.getLogger(__name__)


# The Graph subgraph endpoints for major DEXes
SUBGRAPH_ENDPOINTS = {
    "ethereum": {
        "uniswap_v2": "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v2",
        "uniswap_v3": "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3",
        "sushiswap": "https://api.thegraph.com/subgraphs/name/sushi-v3/v3-ethereum",
    },
    "polygon": {
        "quickswap": "https://api.thegraph.com/subgraphs/name/sushi-v3/v3-polygon",
        "uniswap_v3": "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3-polygon",
    },
    "arbitrum": {
        "uniswap_v3": "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3-arbitrum-one",
        "sushiswap": "https://api.thegraph.com/subgraphs/name/sushi-v3/v3-arbitrum",
    },
    "optimism": {
        "uniswap_v3": "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3-optimism",
    },
    "bsc": {
        "pancakeswap": "https://api.thegraph.com/subgraphs/name/pancakeswap/exchange-v3-bsc",
        "pancakeswap_v2": "https://api.thegraph.com/subgraphs/name/pancakeswap/exchange-v2-bsc",
    }
}


class TheGraphClient:
    """
    Client for querying The Graph subgraphs.
    Provides fast pair discovery without scanning the entire blockchain.
    """
    
    def __init__(self, chain: str = "ethereum", dex: str = "uniswap_v2"):
        self.chain = chain
        self.dex = dex
        self.endpoint = self._get_endpoint()
        self._cache = {}
        self._cache_ttl = 60  # Cache TTL in seconds
        
    def _get_endpoint(self) -> str:
        """Get the subgraph endpoint for the specified chain and DEX"""
        if self.chain not in SUBGRAPH_ENDPOINTS:
            logger.warning(f"Chain {self.chain} not supported, falling back to Ethereum")
            self.chain = "ethereum"
        
        endpoints = SUBGRAPH_ENDPOINTS.get(self.chain, {})
        
        if self.dex not in endpoints:
            # Fallback to first available DEX
            if endpoints:
                self.dex = list(endpoints.keys())[0]
            else:
                return None
        
        return endpoints.get(self.dex)
    
    def query(self, query: str, variables: Dict = None) -> Optional[Dict]:
        """Execute a GraphQL query against the subgraph"""
        if not self.endpoint:
            logger.error(f"No endpoint available for {self.chain}/{self.dex}")
            return None
        
        try:
            response = requests.post(
                self.endpoint,
                json={"query": query, "variables": variables or {}},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            if "errors" in data:
                logger.error(f"GraphQL errors: {data['errors']}")
                return None
            
            return data.get("data")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Subgraph request failed: {e}")
            return None
    
    def get_all_pairs(self, first: int = 1000, skip: int = 0) -> List[Dict]:
        """
        Get all trading pairs from the subgraph.
        Much faster than scanning factory contracts.
        """
        query = """
        query GetPairs($first: Int!, $skip: Int!) {
            pairs(
                first: $first,
                skip: $skip,
                orderBy: volumeUSD,
                orderDirection: desc
            ) {
                id
                token0 {
                    id
                    symbol
                    name
                    decimals
                }
                token1 {
                    id
                    symbol
                    name
                    decimals
                }
                reserve0
                reserve1
                reserveUSD
                volumeUSD
                token0Price
                token1Price
            }
        }
        """
        
        data = self.query(query, {"first": first, "skip": skip})
        if data and "pairs" in data:
            return data["pairs"]
        return []
    
    def get_pairs_for_token(self, token_address: str, first: int = 100) -> List[Dict]:
        """Get all pairs involving a specific token"""
        query = """
        query GetTokenPairs($token: String!, $first: Int!) {
            pairs(
                where: { 
                    or: [
                        { token0: $token },
                        { token1: $token }
                    ]
                },
                first: $first,
                orderBy: reserveUSD,
                orderDirection: desc
            ) {
                id
                token0 {
                    id
                    symbol
                }
                token1 {
                    id
                    symbol
                }
                reserve0
                reserve1
                reserveUSD
                token0Price
                token1Price
            }
        }
        """
        
        data = self.query(query, {"token": token_address.lower(), "first": first})
        if data and "pairs" in data:
            return data["pairs"]
        return []
    
    def get_top_tokens(self, first: int = 50) -> List[Dict]:
        """Get top tokens by volume"""
        query = """
        query GetTopTokens($first: Int!) {
            tokens(
                first: $first,
                orderBy: volumeUSD,
                orderDirection: desc
            ) {
                id
                symbol
                name
                decimals
                volumeUSD
                totalValueLockedUSD
            }
        }
        """
        
        data = self.query(query, {"first": first})
        if data and "tokens" in data:
            return data["tokens"]
        return []
    
    def get_recent_swaps(self, pair_address: str, first: int = 10) -> List[Dict]:
        """Get recent swaps for a specific pair"""
        query = """
        query GetSwaps($pair: String!, $first: Int!) {
            swaps(
                where: { pair: $pair },
                first: $first,
                orderBy: timestamp,
                orderDirection: desc
            ) {
                id
                timestamp
                pair {
                    token0 { symbol }
                    token1 { symbol }
                }
                sender
                amount0In
                amount0Out
                amount1In
                amount1Out
                amountUSD
            }
        }
        """
        
        data = self.query(query, {"pair": pair_address.lower(), "first": first})
        if data and "swaps" in data:
            return data["swaps"]
        return []


class GraphPairBuilder:
    """
    Builds adjacency list for arbitrage scanning using The Graph.
    Much faster than on-chain factory scanning.
    """
    
    def __init__(self, chain: str = "ethereum", dex: str = "uniswap_v2"):
        self.client = TheGraphClient(chain, dex)
        self.chain = chain
        
    def build_graph(self, max_pairs: int = 5000) -> Dict[str, List[str]]:
        """
        Build token adjacency graph from subgraph data.
        Returns: {token_address: [neighbor_token_addresses]}
        """
        graph = {}
        
        # Get top pairs sorted by volume
        pairs = self.client.get_all_pairs(first=max_pairs)
        
        for pair in pairs:
            try:
                token0 = pair.get("token0", {}).get("id", "").lower()
                token1 = pair.get("token1", {}).get("id", "").lower()
                
                if token0 and token1:
                    if token0 not in graph:
                        graph[token0] = []
                    if token1 not in graph:
                        graph[token1] = []
                    
                    graph[token0].append(token1)
                    graph[token1].append(token0)
                    
            except Exception as e:
                logger.debug(f"Error processing pair: {e}")
                continue
        
        logger.info(f"Built graph with {len(graph)} tokens from {len(pairs)} pairs")
        return graph
    
    def get_token_graph(self, token_addresses: List[str]) -> Dict[str, List[str]]:
        """
        Build focused graph for specific tokens.
        More efficient for targeted arbitrage.
        """
        graph = {}
        
        for token in token_addresses:
            pairs = self.client.get_pairs_for_token(token, first=50)
            
            for pair in pairs:
                try:
                    token0 = pair.get("token0", {}).get("id", "").lower()
                    token1 = pair.get("token1", {}).get("id", "").lower()
                    
                    if token0 and token1:
                        if token0 not in graph:
                            graph[token0] = []
                        if token1 not in graph:
                            graph[token1] = []
                        
                        graph[token0].append(token1)
                        graph[token1].append(token0)
                        
                except Exception as e:
                    logger.debug(f"Error processing pair: {e}")
                    continue
        
        return graph


def get_thegraph_client(chain: str, dex: str = None) -> TheGraphClient:
    """Factory function to get a The Graph client"""
    if dex is None:
        # Auto-select best DEX for chain
        dex_map = {
            "ethereum": "uniswap_v2",
            "polygon": "quickswap",
            "arbitrum": "uniswap_v3",
            "optimism": "uniswap_v3",
            "bsc": "pancakeswap"
        }
        dex = dex_map.get(chain, "uniswap_v2")
    
    return TheGraphClient(chain, dex)


# Example usage
"""
# Fast pair discovery using The Graph
client = get_thegraph_client("ethereum", "uniswap_v2")

# Get all pairs (much faster than factory scanning)
pairs = client.get_all_pairs(first=1000)
print(f"Found {len(pairs)} pairs")

# Build arbitrage graph
builder = GraphPairBuilder("ethereum", "uniswap_v2")
graph = builder.build_graph(max_pairs=5000)
print(f"Graph has {len(graph)} tokens")

# Get specific token pairs
weth_pairs = client.get_pairs_for_token("0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2")
print(f"WETH has {len(weth_pairs)} trading pairs")
"""
