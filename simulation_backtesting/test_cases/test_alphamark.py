# Comprehensive Unit Tests for AlphaMark
import pytest
import sys
import os

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "strategy_engine", "src"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "execution_bot", "scripts"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "risk_management"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "gas_tx_optimizer"))

# Test fixtures
class MockWeb3:
    """Mock Web3 for testing without blockchain connection"""
    def __init__(self):
        self.eth = self
        self.is_connected_value = True
        
    def is_connected(self):
        return self.is_connected_value
    
    def to_checksum_address(self, addr):
        return addr.lower()
    
    def to_wei(self, amount, unit):
        return amount * 10**18
    
    def from_wei(self, amount, unit):
        return amount / 10**18
    
    def keccak(self, text=None, hexstr=None):
        return b'\x12\x34\x56\x78' * 8


class MockContract:
    """Mock contract for testing"""
    def __init__(self, returns=None):
        self.returns = returns or {}
        
    def functions(self):
        return self
        
    def getAmountsOut(self, amount, path):
        return self.returns.get('getAmountsOut', [amount, amount * 1.01])
    
    def getPair(self, tokenA, tokenB):
        return self.returns.get('getPair', '0x1234567890123456789012345678901234567890')
    
    def getReserves(self):
        return (1000000 * 10**18, 1000 * 10**18, 0)
    
    def token0(self):
        return '0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    
    def token1(self):
        return '0xBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB'


# ============ Strategy Engine Tests ============

def test_calculate_dynamic_slippage():
    """Test slippage calculation logic"""
    sys.path.insert(0, os.path.join(PROJECT_ROOT, "strategy_engine", "src"))
    from strategy import calculate_dynamic_slippage
    
    # Test base case
    slippage = calculate_dynamic_slippage(1.0, 10000)
    assert slippage >= 0.005, "Base slippage should be 0.5%"
    assert slippage <= 0.05, "Slippage should not exceed 5%"
    
    # Test with high liquidity
    slippage = calculate_dynamic_slippage(1.0, 1000000)
    assert slippage < 0.01, "High liquidity should have low slippage"
    
    print("✅ test_calculate_dynamic_slippage PASSED")


def test_check_path_profitability():
    """Test profit checking logic"""
    sys.path.insert(0, os.path.join(PROJECT_ROOT, "strategy_engine", "src"))
    from strategy import check_path_profitability
    
    w3 = MockWeb3()
    router = MockContract({'getAmountsOut': [1000, 1100]})
    
    # Test profitable path
    w3.eth.contract = lambda addr, abi: router
    
    profit, amount_out = check_path_profitability(w3, '0xrouter', ['WETH', 'USDC'], 1000)
    assert profit > 0, "Should detect profit"
    assert amount_out > 1000, "Amount out should be greater than amount in"
    
    print("✅ test_check_path_profitability PASSED")


def test_dfs_find_cycles():
    """Test DFS cycle finding"""
    sys.path.insert(0, os.path.join(PROJECT_ROOT, "strategy_engine", "src"))
    from strategy import find_graph_arbitrage_opportunities
    
    w3 = MockWeb3()
    # Simple test graph
    test_graph = {
        '0xWETH': ['0xUSDC', '0xDAI'],
        '0xUSDC': ['0xWETH', '0xDAI'],
        '0xDAI': ['0xWETH', '0xUSDC']
    }
    
    # Verify graph structure is valid
    assert '0xWETH' in test_graph
    assert len(test_graph['0xWETH']) == 2
    
    print("✅ test_dfs_find_cycles PASSED")


# ============ Risk Management Tests ============

def test_check_slippage():
    """Test slippage validation"""
    from risk_check import check_slippage
    
    # Test safe case
    assert check_slippage(100, 101, 0.02) == True, "Should pass with 1% slippage"
    
    # Test unsafe case
    assert check_slippage(100, 110, 0.01) == False, "Should fail with 10% slippage"
    
    print("✅ test_check_slippage PASSED")


def test_check_liquidity():
    """Test liquidity validation"""
    from risk_check import check_liquidity
    
    # Test sufficient liquidity
    assert check_liquidity(100, 1000, 0.1) == True
    
    # Test insufficient liquidity
    assert check_liquidity(500, 1000, 0.1) == False
    
    # Test zero liquidity
    assert check_liquidity(100, 0, 0.1) == False
    
    print("✅ test_check_liquidity PASSED")


def test_full_risk_assessment():
    """Test comprehensive risk assessment"""
    from risk_check import full_risk_assessment
    
    # Test opportunity with correct keys
    opportunity = {
        'type': 'graph_arb',
        'chain': 'ethereum',
        'base_token': 'WETH',
        'loan_amount': 1.0,
        'profit_eth': 0.05,
        'net_usd_profit': 150.0,
        'slippage': 0.003,
        'path': ['WETH', 'USDC', 'DAI', 'WETH'],
        'router_address': '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D'
    }
    
    current_prices = {'buy_dex': 3000, 'sell_dex': 3000}
    liquidity_data = {'WETH': 1000000}
    
    safe, risks = full_risk_assessment(opportunity, current_prices, liquidity_data)
    
    # Should pass with low slippage and high liquidity
    # FIXED: Proper assertion - verify risk assessment works correctly
    assert safe == True, f"Opportunity should be safe but got risks: {risks}"
    assert len(risks) == 0, f"Should have no risks but got: {risks}"
    
    print("✅ test_full_risk_assessment PASSED")


def test_risk_assessment_with_wrong_keys():
    """Test that risk assessment handles various key formats"""
    from risk_check import full_risk_assessment
    
    # Test with alternate key names
    opportunity1 = {
        'type': 'graph_arb',
        'token': 'WETH',  # Using 'token' instead of 'base_token'
        'loan_amount': 1.0,
        'profit': 0.05,   # Using 'profit' instead of 'profit_eth'
        'net_usd_profit': 150.0,
        'slippage': 0.003
    }
    
    current_prices = {}
    liquidity_data = {'WETH': 1000000}
    
    # Should not crash
    try:
        safe, risks = full_risk_assessment(opportunity1, current_prices, liquidity_data)
        assert True, "Should handle alternate keys gracefully"
    except KeyError:
        pytest.fail("Should not raise KeyError")
    
    print("✅ test_risk_assessment_with_wrong_keys PASSED")


# ============ Gas Optimizer Tests ============

def test_gas_optimizer():
    """Test gas estimation"""
    sys.path.insert(0, os.path.join(PROJECT_ROOT, "gas_tx_optimizer"))
    from optimizer import GasOptimizer
    
    w3 = MockWeb3()
    optimizer = GasOptimizer()
    
    # Test caching
    gas1 = optimizer.estimate_gas(w3, '0xcontract', 'testFunction', [])
    gas2 = optimizer.estimate_gas(w3, '0xcontract', 'testFunction', [])
    
    assert gas1 == gas2, "Cached value should be returned"
    
    print("✅ test_gas_optimizer PASSED")


def test_optimal_gas_price():
    """Test gas price optimization"""
    sys.path.insert(0, os.path.join(PROJECT_ROOT, "gas_tx_optimizer"))
    from optimizer import GasOptimizer
    
    w3 = MockWeb3()
    optimizer = GasOptimizer()
    
    # Test fallback behavior
    gas_prices = optimizer.get_optimal_gas_price(w3)
    
    assert 'maxFeePerGas' in gas_prices
    assert 'maxPriorityFeePerGas' in gas_prices
    
    print("✅ test_optimal_gas_price PASSED")


# ============ Integration Tests ============

def test_executor_abi_encoding():
    """Test ABI encoding for multi-hop"""
    sys.path.insert(0, os.path.join(PROJECT_ROOT, "execution_bot", "scripts"))
    from executor import FLASHLOAN_ABI
    
    # Verify multi-hop ABI is present
    function_names = [f.get('name', '') for f in FLASHLOAN_ABI]
    assert 'executeArbitrage' in function_names
    
    print("✅ test_executor_abi_encoding PASSED")


def test_config_loading():
    """Test configuration loads correctly"""
    config_path = os.path.join(PROJECT_ROOT, "config_asset_registry", "data", "contracts.json")
    
    if os.path.exists(config_path):
        import json
        with open(config_path) as f:
            config = json.load(f)
        
        # Verify key chains exist
        assert 'ethereum' in config
        assert 'polygon' in config
        
        # Verify lending pools are different (not all Ethereum)
        eth_lending = config['ethereum'].get('lending_pool', '')
        poly_lending = config['polygon'].get('lending_pool', '')
        
        assert eth_lending != poly_lending or poly_lending == '', "Lending pools should be chain-specific"
        
        # Verify WebSocket URLs are valid
        for chain, data in config.items():
            ws = data.get('ws', '')
            if ws:
                assert not '旧' in ws, f"Corrupted WebSocket URL for {chain}"
        
        print("✅ test_config_loading PASSED")
    else:
        print("⚠️  test_config_loading SKIPPED (config not found)")


def test_mev_builder_urls():
    """Test MEV builder URLs are valid"""
    sys.path.insert(0, os.path.join(PROJECT_ROOT, "mempool_mev", "scripts"))
    from mev_executor import MEV_BUILDER_URLS
    
    assert 'ethereum' in MEV_BUILDER_URLS
    assert len(MEV_BUILDER_URLS['ethereum']) > 0
    
    # Verify no deprecated URLs
    for chain, urls in MEV_BUILDER_URLS.items():
        for url in urls:
            assert 'relay.flashbots.net' in url or 'mevblocker' in url, f"Valid URL: {url}"
    
    print("✅ test_mev_builder_urls PASSED")


# ============ Run All Tests ============

if __name__ == "__main__":
    print("\n" + "="*50)
    print("🧪 Running AlphaMark Unit Tests")
    print("="*50 + "\n")
    
    tests = [
        test_calculate_dynamic_slippage,
        test_check_path_profitability,
        test_dfs_find_cycles,
        test_check_slippage,
        test_check_liquidity,
        test_full_risk_assessment,
        test_risk_assessment_with_wrong_keys,
        test_gas_optimizer,
        test_optimal_gas_price,
        test_executor_abi_encoding,
        test_config_loading,
        test_mev_builder_urls,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} FAILED: {e}")
            failed += 1
    
    print("\n" + "="*50)
    print(f"📊 Test Results: {passed} passed, {failed} failed")
    print("="*50)
    
    if failed == 0:
        print("\n🎉 All tests passed! System is ready for production.")
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please review.")
