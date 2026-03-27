// SPDX-License-Identifier: MIT
pragma solidity ^0.8.10;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

// Aave V3 Pool Interface
interface IPool {
    function flashLoanSimple(
        address receiverAddress,
        address asset,
        uint256 amount,
        bytes calldata params,
        uint16 referralCode
    ) external;
}

// Uniswap V2 Router Interface
interface IUniswapV2Router02 {
    function swapExactTokensForTokens(
        uint amountIn,
        uint amountOutMin,
        address[] calldata path,
        address to,
        uint deadline
    ) external returns (uint[] memory amounts);
}

// Uniswap V3 Router Interface
interface IUniswapV3Router {
    struct ExactInputSingleParams {
        address tokenIn;
        address tokenOut;
        uint24 fee;
        address recipient;
        uint256 deadline;
        uint256 amountIn;
        uint256 amountOutMinimum;
        uint160 sqrtPriceLimitX96;
    }
    function exactInputSingle(ExactInputSingleParams calldata params) external payable returns (uint256 amountOut);
    
    // For multi-hop: path can be encoded as bytes
    function exactInput(bytes calldata path, address recipient, uint256 amountIn, uint256 amountOutMinimum) external payable returns (uint256 amountOut);
}

// Uniswap V3 Pool Interface for getting slot0 data
interface IUniswapV3Pool {
    function slot0() external view returns (uint160 sqrtPriceX96, int24 tick, uint16 observationIndex, uint16 observationCardinality, uint16 observationCardinalityNext, uint8 feeProtocol, bool unlocked);
    function token0() external view returns (address);
    function token1() external view returns (address);
}

contract FlashLoan {
    using SafeERC20 for IERC20;

    address public owner;
    IPool public immutable POOL; // Aave V3 Pool
    
    // Maximum hops for multi-hop arbitrage
    uint256 public constant MAX_HOPS = 5;
    
    // Minimum profit threshold (in wei) to make the trade worthwhile
    uint256 public constant MIN_PROFIT_WEI = 1e15; // 0.001 ETH

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner can call this function");
        _;
    }

    constructor(address _poolAddress) {
        owner = msg.sender;
        POOL = IPool(_poolAddress);
    }

    /**
     * @notice Initiates the flash loan arbitrage with multi-hop support.
     * @param tokenToBorrow The address of the token to borrow.
     * @param amount The amount of the token to borrow.
     * @param params ABI-encoded parameters for the multi-hop arbitrage logic.
     *               Format: abi.encode(uint256 amountOutMin, address[] memory path, address[] memory routers, uint256[] memory fees)
     *               - path: array of token addresses for the swap path
     *               - routers: array of router addresses (use address(0) for Uniswap V3)
     *               - fees: fee tiers for V3 pools (ignored for V2)
     */
    function executeArbitrage(
        address tokenToBorrow,
        uint256 amount,
        bytes calldata params
    ) external {
        address receiverAddress = address(this);

        // Call the flash loan function on the Aave pool, passing params to the callback
        POOL.flashLoanSimple(receiverAddress, tokenToBorrow, amount, params, 0);
    }

    /**
     * @notice This is the callback function that Aave's pool will call.
     * @param asset The address of the token that was borrowed.
     * @param amount The amount of the token that was borrowed.
     * @param premium The fee to be paid for the flash loan.
     * @param initiator The address that initiated the flash loan.
     * @param params The parameters passed from the initial call.
     * @return bool Returns true if the flash loan was successful.
     */
    function executeOperation(
        address asset,
        uint256 amount,
        uint256 premium,
        address initiator,
        bytes calldata params
    ) external returns (bool) {
        // Ensure the call is coming from the Aave pool
        require(msg.sender == address(POOL), "Caller is not Aave Pool");

        // --- DECODE PARAMS for multi-hop arbitrage ---
        // Format: abi.encode(amountOutMin, path, routers, fees)
        // path: [token0, token1, token2, ...] - the swap path
        // routers: [router1, router2, ...] - corresponding routers for each swap
        // fees: [fee1, fee2, ...] - fee tiers for Uniswap V3 (0 for V2)
        (uint256 amountOutMin, address[] memory path, address[] memory routers, uint256[] memory fees) = 
            abi.decode(params, (uint256, address[], address[], uint256[]));

        // Validate the path
        require(path.length >= 2, "Invalid path length");
        require(path.length - 1 == routers.length, "Routers length mismatch");
        require(path.length - 1 == fees.length, "Fees length mismatch");
        
        // Record starting balance of the borrowed asset to calculate profit after swaps
        uint256 startBalance = IERC20(asset).balanceOf(address(this));
        
        // Approve the borrowed asset for the first swap
        IERC20(asset).safeApprove(routers[0], amount);

        // --- EXECUTE MULTI-HOP ARBITRAGE ---
        uint256 amountToSwap = amount;
        
        for (uint256 i = 0; i < routers.length; i++) {
            address router = routers[i];
            address tokenIn = path[i];
            address tokenOut = path[i + 1];
            uint256 fee = fees[i];
            
            // Reset and set approval for this swap
            IERC20(tokenIn).forceApprove(router, 0);
            IERC20(tokenIn).safeApprove(router, amountToSwap);
            
            // Check if this is a Uniswap V3 router (address(0) or explicitly V3)
            bool isV3 = (router == address(0));
            
            if (isV3) {
                // Uniswap V3 swap - use fee tier from fees array
                // fees[i] contains the V3 pool fee tier (e.g., 3000 for 0.3%)
                uint24 v3Fee = uint24(fees[i]);
                
                // Use default Uniswap V3 router if not specified
                router = 0xE592427A0AEce92De3Edee1F18E0157C05861564;
                
                // For V3, we encode the path as: tokenIn -> fee -> tokenOut
                bytes memory path = abi.encodePacked(tokenIn, v3Fee, tokenOut);
                
                // For the last swap, use amountOutMin; for others use 0
                uint256 minOut = (i == routers.length - 1) ? amountOutMin : 1;
                
                try IUniswapV3Router(router).exactInput(
                    path,
                    address(this),
                    amountToSwap,
                    minOut
                ) returns (uint256 amountOut) {
                    amountToSwap = amountOut;
                } catch {
                    require(false, "V3 swap failed");
                }
            } else {
                // Uniswap V2 / SushiSwap / PancakeSwap swap
                address[] memory swapPath = new address[](2);
                swapPath[0] = tokenIn;
                swapPath[1] = tokenOut;
                
                // For the last swap, use amountOutMin; for others use 0
                uint256 minOut = (i == routers.length - 1) ? amountOutMin : 1;
                
                try IUniswapV2Router02(router).swapExactTokensForTokens(
                    amountToSwap,
                    minOut,
                    swapPath,
                    address(this),
                    block.timestamp
                ) returns (uint[] memory amounts) {
                    amountToSwap = amounts[amounts.length - 1];
                } catch {
                    require(false, "V2 swap failed");
                }
            }
        }

        // --- VERIFY PROFIT BEFORE REPAYMENT ---
        uint256 endBalance = IERC20(path[path.length - 1]).balanceOf(address(this));
        uint256 profit = endBalance;
        
        // Calculate amount to repay (original + premium)
        uint256 amountToRepay = amount + premium;
        
        // Get the final token (last in path)
        address finalToken = path[path.length - 1];
        
        // If final token is different from borrowed asset, we need to swap back
        if (finalToken != asset) {
            // Swap profit back to original asset for repayment
            IERC20(finalToken).safeApprove(routers[routers.length - 1], endBalance);
            
            address[] memory revertPath = new address[](2);
            revertPath[0] = finalToken;
            revertPath[1] = asset;
            
            // Get expected amount out for repayment
            try IUniswapV2Router02(routers[routers.length - 1]).getAmountsOut(endBalance, revertPath) returns (uint[] memory revertAmounts) {
                uint256 minRepay = revertAmounts[revertAmounts.length - 1];
                
                if (minRepay < amountToRepay) {
                    // Not enough to repay - will fail
                    require(false, "Insufficient repayment");
                }
                
                // Execute the swap back with proper slippage protection (0.5%)
                uint256 minRepayWithSlippage = (amountToRepay * 995) / 1000;
                IUniswapV2Router02(routers[routers.length - 1]).swapExactTokensForTokens(
                    endBalance,
                    minRepayWithSlippage,
                    revertPath,
                    address(this),
                    block.timestamp
                );
                
                // Update balance to remaining profit
                endBalance = IERC20(asset).balanceOf(address(this));
            } catch {
                require(false, "Repayment swap failed");
            }
        } else {
            // Final token is same as borrowed - check if we have enough
            require(endBalance >= amountToRepay, "Insufficient funds to repay flash loan");
        }

        // --- REPAY THE FLASH LOAN ---
        uint256 repayAmount = amount + premium;
        IERC20(asset).safeApprove(address(POOL), repayAmount);

        // Transfer profit to owner
        uint256 actualProfit = IERC20(asset).balanceOf(address(this)) - repayAmount;
        if (actualProfit > 0) {
            IERC20(asset).safeTransfer(owner, actualProfit);
        }

        return true;
    }

    /**
     * @notice Execute a simple single-hop arbitrage (backward compatible)
     * @param tokenToBorrow Token to borrow
     * @param amount Amount to borrow
     * @param amountOutMin Minimum output amount
     * @param path Swap path (2 elements for single hop)
     * @param router Router address
     */
    function executeSimpleArbitrage(
        address tokenToBorrow,
        uint256 amount,
        uint256 amountOutMin,
        address[] memory path,
        address router
    ) external onlyOwner {
        // Build params for simple single-hop
        address[] memory routers = new address[](1);
        routers[0] = router;
        uint256[] memory fees = new uint256[](1);
        fees[0] = 0;
        
        bytes memory params = abi.encode(amountOutMin, path, routers, fees);
        
        POOL.flashLoanSimple(address(this), tokenToBorrow, amount, params, 0);
    }

    function withdraw(address _tokenAddress) external onlyOwner {
        IERC20 token = IERC20(_tokenAddress);
        uint256 balance = token.balanceOf(address(this));
        token.safeTransfer(owner, balance);
    }

    function approveToken(address _token, address _spender, uint256 _amount) external onlyOwner {
        IERC20(_token).safeApprove(_spender, 0); // Safety reset
        IERC20(_token).safeApprove(_spender, _amount);
    }

    receive() external payable {}
}
