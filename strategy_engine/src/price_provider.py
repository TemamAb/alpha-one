import logging
import os
import time
from typing import Dict, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

SESSION = requests.Session()
ADAPTER = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
SESSION.mount("http://", ADAPTER)
SESSION.mount("https://", ADAPTER)

PRICE_CACHE: Dict[str, Dict[str, float]] = {}
PROVIDER_STATUS: Dict[str, Dict[str, float]] = {}
CACHE_TTL_SECONDS = int(os.environ.get("PRICE_CACHE_TTL_SECONDS", "20"))

COINGECKO_IDS = {
    "ETH-USD": "ethereum",
    "BTC-USD": "bitcoin",
    "MATIC-USD": "matic-network",
    "BNB-USD": "binancecoin",
    "AVAX-USD": "avalanche-2",
    "FTM-USD": "fantom",
    "CELO-USD": "celo",
    "MNT-USD": "mantle",
    "SEI-USD": "sei-network",
    "DAI-USD": "dai"
}

CHAIN_SYMBOLS = {
    "ethereum": "ETH-USD",
    "arbitrum": "ETH-USD",
    "optimism": "ETH-USD",
    "base": "ETH-USD",
    "linea": "ETH-USD",
    "scroll": "ETH-USD",
    "zksync_era": "ETH-USD",
    "blast": "ETH-USD",
    "manta_pacific": "ETH-USD",
    "zora": "ETH-USD",
    "mode": "ETH-USD",
    "berachain": "ETH-USD",
    "polygon": "MATIC-USD",
    "bsc": "BNB-USD",
    "avalanche": "AVAX-USD",
    "gnosis": "DAI-USD",
    "fantom": "FTM-USD",
    "celo": "CELO-USD",
    "mantle": "MNT-USD",
    "sei_evm": "SEI-USD"
}

CHAIN_TOKEN_ADDRESSES = {
    "ethereum": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    "arbitrum": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
    "optimism": "0x4200000000000000000000000000000000000006",
    "base": "0x4200000000000000000000000000000000000006",
    "linea": "0xe5D7C2a44b7f2c4f6dEf0bA0D4bB1b8C6fA9A4b1",
    "scroll": "0x5300000000000000000000000000000000000004",
    "zksync_era": "0x5aea5775959fbc2557cc8789bc1bf90a239d9a91",
    "blast": "0x4300000000000000000000000000000000000004",
    "manta_pacific": "0x0Dc808adcE2099A9F62AA87D9670745AbA741746",
    "mode": "0x4200000000000000000000000000000000000006",
    "zora": "0x4200000000000000000000000000000000000006",
    "polygon": "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",
    "bsc": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
    "avalanche": "0xB31f66AA3C1C785363F0875A1B74E27b85FD66c7",
    "gnosis": "0xe91D153E0b41518A2Ce8Dd3D7944Fa863463a97d",
    "fantom": "0x21be370d5312f44cb42ce377bc9b8a0cef1a4c83",
    "celo": "0x471EcE3750Da237f93B8E339c536989b8978a438",
    "mantle": "0xdEAddEaDdeadDEadDEADDEAddEADDEAddead1111",
    "berachain": "0x6969696969696969696969696969696969696969",
    "sei_evm": "0x160345fC359604fC6e70E3c5fAcbdE5F7A9342d8"
}

STATIC_FALLBACKS = {
    "ETH-USD": 3000.0,
    "BTC-USD": 60000.0,
    "MATIC-USD": 0.70,
    "BNB-USD": 400.0,
    "AVAX-USD": 35.0,
    "FTM-USD": 0.6,
    "CELO-USD": 0.8,
    "MNT-USD": 1.0,
    "SEI-USD": 0.5,
    "DAI-USD": 1.0
}


def _cache_get(symbol: str) -> Optional[Dict[str, float]]:
    cached = PRICE_CACHE.get(symbol)
    if not cached:
        return None
    if (time.time() - cached["timestamp"]) > CACHE_TTL_SECONDS:
        return None
    return cached


def _cache_set(symbol: str, price: float, provider: str) -> Dict[str, float]:
    record = {
        "symbol": symbol,
        "price": float(price),
        "provider": provider,
        "timestamp": time.time(),
        "degraded": provider == "static_fallback",
    }
    PRICE_CACHE[symbol] = record
    PROVIDER_STATUS[provider] = {"ok": 1, "timestamp": record["timestamp"]}
    return record


def _record_provider_failure(provider: str, error: Exception) -> None:
    PROVIDER_STATUS[provider] = {
        "ok": 0,
        "timestamp": time.time(),
        "error": str(error),
    }


def _fetch_coinbase(symbol: str) -> Optional[float]:
    response = SESSION.get(f"https://api.coinbase.com/v2/prices/{symbol}/spot", timeout=5)
    response.raise_for_status()
    data = response.json()
    return float(data["data"]["amount"])


def _fetch_coingecko(symbol: str) -> Optional[float]:
    coin_id = COINGECKO_IDS.get(symbol)
    if not coin_id:
        return None
    response = SESSION.get(
        f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd",
        timeout=5,
    )
    response.raise_for_status()
    data = response.json()
    price = float(data.get(coin_id, {}).get("usd", 0))
    return price if price > 0 else None


def _fetch_dexscreener(chain: str) -> Optional[float]:
    token_address = CHAIN_TOKEN_ADDRESSES.get(chain)
    if not token_address:
        return None
    response = SESSION.get(
        f"https://api.dexscreener.com/latest/dex/tokens/{token_address}",
        timeout=5,
    )
    response.raise_for_status()
    data = response.json()
    pairs = data.get("pairs") or []
    usd_prices = []
    for pair in pairs:
        pair_chain = str(pair.get("chainId", "")).lower()
        if chain and pair_chain and chain not in pair_chain and pair_chain != chain:
            continue
        price_usd = pair.get("priceUsd")
        try:
            if price_usd is not None:
                usd_prices.append(float(price_usd))
        except (TypeError, ValueError):
            continue
    return max(usd_prices) if usd_prices else None


def get_price(symbol: Optional[str] = None, chain: Optional[str] = None) -> Dict[str, float]:
    resolved_symbol = symbol or CHAIN_SYMBOLS.get(chain or "", "ETH-USD")
    cached = _cache_get(resolved_symbol)
    if cached:
        return cached

    provider_attempts = [
        ("coinbase", lambda: _fetch_coinbase(resolved_symbol)),
        ("coingecko", lambda: _fetch_coingecko(resolved_symbol)),
    ]

    if chain:
        provider_attempts.append(("dexscreener", lambda: _fetch_dexscreener(chain)))

    for provider_name, loader in provider_attempts:
        try:
            price = loader()
            if price and price > 0:
                logger.info(f"[PRICE] {resolved_symbol} sourced from {provider_name}: ${price:.4f}")
                return _cache_set(resolved_symbol, price, provider_name)
        except Exception as exc:
            _record_provider_failure(provider_name, exc)
            logger.warning(f"[PRICE] {provider_name} failed for {resolved_symbol}: {exc}")

    fallback_price = STATIC_FALLBACKS.get(resolved_symbol, STATIC_FALLBACKS["ETH-USD"])
    logger.warning(f"[PRICE] Using static fallback for {resolved_symbol}: ${fallback_price:.4f}")
    return _cache_set(resolved_symbol, fallback_price, "static_fallback")


def get_chain_price(chain: str) -> float:
    return float(get_price(chain=chain)["price"])


def get_provider_status() -> Dict[str, Dict[str, float]]:
    return PROVIDER_STATUS.copy()
