# Chain Onboarding Checklist

Use this checklist before adding any new production chain to `contracts.json`.

## Required

- chain name and canonical id chosen
- chain RPC validated under production scan load
- secondary RPC validated
- wrapped native token address confirmed
- at least one router address confirmed
- at least one factory address confirmed
- token universe defined
- `getAmountsOut` smoke test passed
- factory pair-length call validated
- graph build smoke test passed
- gas-price read validated
- native token USD price source mapped
- execution path compatibility reviewed

## Promotion States

- `planned`
- `config_ready`
- `validated`
- `integrated`

## Promotion Rule

A chain must not move to `integrated` until:

- graph building works on live RPCs
- routing is validated
- risk checks run without malformed data
- dashboard metrics remain stable with the chain enabled
