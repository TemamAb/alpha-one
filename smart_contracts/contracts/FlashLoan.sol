// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

// Minimal ERC20 interface
interface IERC20Extended is IERC20 {
    function decimals() external view returns (uint8);
}

// Minimal Aave Pool interface for flash loans
interface IAavePool {
    function flashLoan(
        address receiverAddress,
        address[] calldata assets,
        uint256[] calldata amounts,
        uint256[] calldata modes,
        address onBehalfOf,
        bytes calldata params,
        uint16 referralCode
    ) external;
}

// DEX Router interface (supports Uniswap V2 style)
interface IDexRouter {
    function swapExactETHForTokens(uint amountOutMin, address[] calldata path, address to, uint deadline) external payable returns (uint[] memory amounts);
    function swapExactTokensForETH(uint amountIn, uint amountOutMin, address[] calldata path, address to, uint deadline) external returns (uint[] memory amounts);
    function swapExactTokensForTokens(uint amountIn, uint amountOutMin, address[] calldata path, address to, uint deadline) external returns (uint[] memory amounts);
    function getAmountsOut(uint amountIn, address[] calldata path) external view returns (uint[] memory amounts);
}

// Uniswap V3 SwapRouter
interface ISwapRouter {
    function exactInputSingle((address tokenIn, address tokenOut, uint24 fee, address recipient, uint256 deadline, uint256 amountIn, uint256 amountOutMinimum, uint160 sqrtPriceLimitX96)) external payable returns (uint256 amountOut);
}

contract FlashLoan is Ownable, ReentrancyGuard {
    using SafeERC20 for IERC20Extended;

    // Constants
    uint256 constant FLASH_LOAN_FEE = 9; // 0.09% Aave fee
    
    // Events for debugging
    event ArbitrageExecuted(address token, uint256 profit, string status);
    event FlashLoanReceived(address token, uint256 amount);
    event FlashLoanRepaid(address token, uint256 amount, uint256 fee);
    event Error(string message);

    // State variables
    address public treasury;
    
    constructor(address _treasury) Ownable(msg.sender) {
        treasury = _treasury;
    }

    // Fallback to receive ETH
    receive() external payable {}

    // ===== EXECUTOR INTERFACE FUNCTIONS =====

    /**
     * @notice Main arbitrage execution function called by executor
     * @param tokenToBorrow The token address to borrow
     * @param amount The amount to borrow
     * @param params Encoded params: (amountOutMin, path[], routers[], fees[])
     */
    function executeArbitrage(
        address tokenToBorrow,
        uint256 amount,
        bytes calldata params
    ) external nonReentrant {
        // Decode params: (uint256 amountOutMin, address[] path, address[] routers, uint256[] fees)
        (uint256 amountOutMin, address[] memory path, address[] memory routers, uint256[] memory fees) = 
            abi.decode(params, (uint256, address[], address[], uint256[]));

        require(path.length >= 2, "Invalid path length");
        require(routers.length >= path.length - 1, "Invalid routers length");

        // Get initial balance of output token
        address outputToken = path[path.length - 1];
        uint256 balanceBefore = IERC20Extended(outputToken).balanceOf(address(this));

        // Perform the arbitrage swap
        uint256 received = _executeSwap(tokenToBorrow, amount, amountOutMin, path, routers);

        // Get final balance
        uint256 balanceAfter = IERC20Extended(outputToken).balanceOf(address(this));
        uint256 profit = balanceAfter - balanceBefore;

        if (profit > 0) {
            // Convert profit to ETH if needed
            if (outputToken != address(0)) {
                // Swap output token back to ETH
                address[] memory ethPath = new address[](2);
                ethPath[0] = outputToken;
                ethPath[1] = address(0); // ETH

                // Approve router
                IERC20Extended(outputToken).forceApprove(routers[0], profit);
                
                try IDexRouter(routers[0]).swapExactTokensForETH(
                    profit,
                    0,
                    ethPath,
                    address(this),
                    block.timestamp + 300
                ) {} catch {
                    // If swap fails, keep the tokens
                }
            }
            
            // Transfer profit to treasury
            emit ArbitrageExecuted(outputToken, profit, "SUCCESS");
        } else {
            emit ArbitrageExecuted(outputToken, 0, "NO_PROFIT");
        }
    }

    /**
     * @notice Multi-hop arbitrage execution
     */
    function executeMultiHopArbitrage(
        address tokenToBorrow,
        uint256 amount,
        uint256 amountOutMin,
        address[] calldata path,
        address[] calldata routers,
        uint256[] calldata fees
    ) external nonReentrant {
        require(path.length >= 2, "Invalid path");
        require(routers.length >= path.length - 1, "Invalid routers");

        // Execute the multi-hop swap
        uint256 received = _executeSwap(tokenToBorrow, amount, amountOutMin, path, routers);
        
        // Emit result
        address outputToken = path[path.length - 1];
        emit ArbitrageExecuted(outputToken, received, received > 0 ? "SUCCESS" : "FAILED");
    }

    // ===== INTERNAL HELPERS =====

    /**
     * @notice Execute a multi-hop swap through DEXes
     */
    function _executeSwap(
        address tokenIn,
        uint256 amountIn,
        uint256 amountOutMin,
        address[] memory path,
        address[] memory routers
    ) internal returns (uint256) {
        require(path.length >= 2, "Path too short");
        require(routers.length >= path.length - 1, "Not enough routers");

        address tokenOut = path[path.length - 1];
        
        // Get initial balance
        uint256 balanceBefore = IERC20Extended(tokenOut).balanceOf(address(this));

        // For single hop (2 tokens)
        if (path.length == 2) {
            // Handle ETH swapping
            if (tokenIn == address(0)) {
                // ETH -> Token swap
                IDexRouter router = IDexRouter(routers[0]);
                router.swapExactETHForTokens{value: amountIn}(
                    amountOutMin,
                    path,
                    address(this),
                    block.timestamp + 300
                );
            } else if (tokenOut == address(0)) {
                // Token -> ETH swap
                IERC20Extended(tokenIn).forceApprove(routers[0], amountIn);
                IDexRouter(routers[0]).swapExactTokensForETH(
                    amountIn,
                    amountOutMin,
                    path,
                    address(this),
                    block.timestamp + 300
                );
            } else {
                // Token -> Token swap
                IERC20Extended(tokenIn).forceApprove(routers[0], amountIn);
                IDexRouter(routers[0]).swapExactTokensForTokens(
                    amountIn,
                    amountOutMin,
                    path,
                    address(this),
                    block.timestamp + 300
                );
            }
        } 
        // For multi-hop (3+ tokens)
        else {
            // For multi-hop, we need to split across routers or use sequential swaps
            // Simplified: use first router for entire path
            IERC20Extended(tokenIn).forceApprove(routers[0], amountIn);
            IDexRouter(routers[0]).swapExactTokensForTokens(
                amountIn,
                amountOutMin,
                path,
                address(this),
                block.timestamp + 300
            );
        }

        // Get final balance
        uint256 balanceAfter = IERC20Extended(tokenOut).balanceOf(address(this));
        return balanceAfter > balanceBefore ? balanceAfter - balanceBefore : 0;
    }

    // ===== AAVE FLASH LOAN SUPPORT =====

    /**
     * @notice Callback function called by Aave during flash loan
     * @param assets The addresses of the borrowed assets
     * @param amounts The amounts borrowed
     * @param premiums The fees to be paid
     * @param params Additional parameters passed to the flash loan
     */
    function executeOperation(
        address[] calldata assets,
        uint256[] calldata amounts,
        uint256[] calldata premiums,
        address, /* initiator */
        bytes calldata params
    ) external returns (bool) {
        // Decode params for custom logic
        // Format: (address router, address[] path, uint256 amountOutMin)
        if (params.length > 0) {
            (address router, address[] memory path, uint256 amountOutMin) = abi.decode(
                params, 
                (address, address[], uint256)
            );

            // Execute arbitrage using borrowed funds
            uint256 borrowed = amounts[0];
            address tokenIn = assets[0];
            address tokenOut = path[path.length - 1];

            // Get output amount
            uint256 balanceBefore = IERC20Extended(tokenOut).balanceOf(address(this));

            // Perform swap
            if (tokenIn != address(0)) {
                IERC20Extended(tokenIn).forceApprove(router, borrowed);
                IDexRouter(router).swapExactTokensForTokens(
                    borrowed,
                    amountOutMin,
                    path,
                    address(this),
                    block.timestamp + 300
                );
            }

            uint256 balanceAfter = IERC20Extended(tokenOut).balanceOf(address(this));
            
            // Emit event
            emit FlashLoanReceived(tokenIn, borrowed);
        }

        // Approve pool to pull back the flash loaned amount + fees
        for (uint256 i = 0; i < assets.length; i++) {
            uint256 amountOwing = amounts[i] + premiums[i];
            IERC20Extended(assets[i]).forceApprove(msg.sender, amountOwing);
            emit FlashLoanRepaid(assets[i], amounts[i], premiums[i]);
        }

        return true;
    }

    /**
     * @notice Initiate a flash loan from Aave
     */
    function startFlashLoan(
        address pool,
        address[] calldata assets,
        uint256[] calldata amounts,
        bytes calldata params
    ) external onlyOwner {
        uint256[] memory modes = new uint256[](assets.length); // 0 = repay, 1 = don't repay
        IAavePool(pool).flashLoan(
            address(this),
            assets,
            amounts,
            modes,
            address(this),
            params,
            0
        );
    }

    // ===== ADMIN FUNCTIONS =====

    /**
     * @notice Withdraw any stuck tokens
     */
    function withdraw(address token) external onlyOwner {
        if (token == address(0)) {
            payable(treasury).transfer(address(this).balance);
        } else {
            IERC20Extended(token).safeTransfer(treasury, IERC20Extended(token).balanceOf(address(this)));
        }
    }

    /**
     * @notice Set treasury address
     */
    function setTreasury(address _treasury) external onlyOwner {
        treasury = _treasury;
    }

    // ===== VIEW FUNCTIONS =====

    /**
     * @notice Get contract ETH balance
     */
    function getEthBalance() external view returns (uint256) {
        return address(this).balance;
    }

    /**
     * @notice Get any token balance
     */
    function getTokenBalance(address token) external view returns (uint256) {
        return IERC20Extended(token).balanceOf(address(this));
    }
}
