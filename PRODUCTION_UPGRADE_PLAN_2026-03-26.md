# AlphaMark Production Upgrade Plan

Date: 2026-03-26

## Current Reality

- Production-integrated chains today: 7
- Current chains: ethereum, polygon, bsc, arbitrum, optimism, base, avalanche
- Live stack status: dashboard, Redis, and bot run in production mode
- Live scanning status: operational, but opportunity generation remains constrained by RPC quality, bad factories, and limited validated graph sources

## KPI File Review

`KPI_COMPARISON.md` is aspirational, not operationally validated.

Observed gaps versus the current live system:

- Latency is not measured end-to-end in production with audited traces.
- Scanning capacity is not demonstrated at the market-leader level in live conditions.
- Execution runtime is functional, but live profitable execution has not been empirically validated in this session.
- Mempool visibility is not equivalent to direct peering.
- Gas strategy is partially dynamic, but still falls back to hardcoded values on some chains.
- Deployment readiness is improved, but not yet equivalent to a fully proven production searcher.

Conclusion:

- The KPI document should be treated as a target state.
- Production metrics must be generated from measured telemetry, not static claims.

## Price Provider Analysis

AlphaMark needs a dedicated real-time price provider layer for three reasons:

1. Native token gas-cost valuation currently depends on a thin fallback chain.
2. Profit thresholds and ROI filters are only as good as the underlying price feeds.
3. Chain expansion to 20 chains requires a consistent, cache-aware pricing abstraction.

### Recommended Free Provider Stack

Primary goals:

- free or low-cost
- simple public access
- good uptime
- safe degradation path

Recommended provider order:

1. Coinbase spot price API
   - good for major assets like ETH and BTC
   - simple public endpoint
2. CoinGecko simple price API
   - broad asset coverage
   - good general fallback
3. DexScreener token-pair pricing
   - useful for chain-native token fallback and DEX-implied prices
   - especially valuable when centralized price APIs lag or are unavailable
4. static emergency fallback
   - last resort only
   - should be visibly marked as degraded mode

### Implementation Requirements

- per-symbol cache TTL
- provider health tracking
- provider attribution in logs/metrics
- safe chain-to-symbol mapping
- degraded-mode warnings when only emergency fallback is available

## Chain Expansion Review

Target: expand from 7 integrated production chains to a top-20 chain set.

Recommended top-20 production target set for AlphaMark:

1. ethereum
2. arbitrum
3. base
4. optimism
5. polygon
6. bsc
7. avalanche
8. linea
9. scroll
10. zksync_era
11. blast
12. manta_pacific
13. mode
14. zora
15. gnosis
16. fantom
17. celo
18. mantle
19. berachain
20. sei_evm

Selection criteria:

- active DeFi liquidity
- stable RPC availability
- viable DEX/factory coverage
- practical arbitrage search relevance
- EVM compatibility for near-term rollout

## Performance Metrics Upgrade

Metrics that must become first-class production telemetry:

- tick-to-trade latency
- RPC latency per chain
- graph build duration per chain and factory
- opportunities found per scan cycle
- opportunities rejected by risk filter
- queue depth
- execution success rate
- realized profit per trade
- profit per hour
- gas cost per successful execution
- fallback-provider usage rate
- degraded-mode incidents

## Phased Implementation Plan

### Phase 1: Pricing Foundation

- add a dedicated price-provider module
- support Coinbase, CoinGecko, DexScreener, and emergency fallback
- add cache and provider health state
- wire strategy profit threshold and gas-cost valuation to the provider layer

### Phase 2: KPI Truthfulness

- replace static KPI claims with measured values where possible
- expose real production metrics in the dashboard
- flag estimated versus measured metrics clearly

### Phase 3: Chain Expansion Framework

- add a chain-onboarding checklist
- require validated RPCs, routers, factories, native wrapped token, and token universe
- stage rollout from 7 to 10, then 15, then 20 chains

### Phase 4: Opportunity Quality

- validate per-chain factory allowlists
- prune unreliable factories
- expand token universes only where liquidity and routing quality are proven
- log why opportunities are rejected

### Phase 5: Live Execution Validation

- confirm repeated opportunity discovery
- confirm successful live executions
- confirm post-gas profitability
- confirm transfer/withdrawal path to user wallet

## Immediate Next Actions

1. implement the new price-provider layer
2. wire the strategy engine to it
3. surface provider source and degraded-mode telemetry to the dashboard
4. then begin the top-20 chain onboarding framework
