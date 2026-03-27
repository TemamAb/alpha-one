pragma solidity ^0.8.20;
// SPDX-License-Identifier: MIT

import "@aave/core-v3/contracts/flashloan/base/FlashLoanReceiverBase.sol";
import "@aave/core-v3/contracts/interfaces/IPoolAddressesProvider.sol";
import "@aave/core-v3/contracts/interfaces/IPool.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

interface IDexRouter {
    function swapExactTokensForTokens(
        uint amountIn,
        uint amountOutMin,
        address[] calldata path,
        address to,
        uint deadline
    ) external returns (uint[] memory amounts);
}

contract CrossChainFlashLoan is FlashLoanReceiverBase {
    address owner;

    constructor(IPoolAddressesProvider provider) FlashLoanReceiverBase(provider) {
        owner = msg.sender;
    }

    modifier onlyOwner() {
        require(msg.sender == owner, "Not owner");
        _;
    }

    function executeOperation(
        address[] calldata assets,
        uint256[] calldata amounts,
        uint256[] calldata premiums,
        address initiator,
        bytes calldata params
    ) external override returns (bool) {
        (address buyDex, address sellDex, address token, uint minProfit, address tokenOut) = abi.decode(params, (address,address,address,uint,address));

        IERC20(token).approve(buyDex, amounts[0]);
        
        address[] memory path = new address[](2);
        path[0] = token;
        path[1] = tokenOut;

        // Swap on buyDex
        IDexRouter(buyDex).swapExactTokensForTokens(
            amounts[0],
            0,
            path,
            address(this),
            block.timestamp
        );

        uint tokenOutBalance = IERC20(tokenOut).balanceOf(address(this));
        IERC20(tokenOut).approve(sellDex, tokenOutBalance);

        // Swap back on sellDex
        address[] memory path2 = new address[](2);
        path2[0] = tokenOut;
        path2[1] = token;
        IDexRouter(sellDex).swapExactTokensForTokens(
            tokenOutBalance,
            minProfit,
            path2,
            address(this),
            block.timestamp
        );

        // Ensure repayment
        for(uint i=0;i<assets.length;i++){
            uint amountOwing = amounts[i]+premiums[i];
            IERC20(assets[i]).approve(address(POOL), amountOwing);
        }
        return true;
    }

    function startFlashLoan(
        address pool,
        address[] calldata assets,
        uint256[] calldata amounts,
        bytes calldata params
    ) external onlyOwner {
        IPool(pool).flashLoan(
            address(this),
            assets,
            amounts,
            new uint256[](assets.length),
            address(this),
            params,
            0
        );
    }
}
