// SPDX-License-Identifier: MIT
pragma solidity ^0.8.10;

/**
 * @title Multicall
 * @notice Aggregate multiple calls into a single transaction
 * @dev Reduces gas costs by batching contract interactions
 */
contract Multicall {
    
    struct Call {
        address target;
        bytes callData;
    }
    
    struct Result {
        bool success;
        bytes returnData;
    }
    
    /**
     * @notice Aggregate multiple calls into one transaction
     * @param calls Array of Call structs containing target address and encoded function data
     * @return results Array of Result structs with success status and return data
     */
    function aggregate(Call[] memory calls) public returns (Result[] memory results) {
        results = new Result[](calls.length);
        
        for (uint256 i = 0; i < calls.length; i++) {
            (bool success, bytes memory result) = calls[i].target.call(calls[i].callData);
            results[i] = Result(success, result);
        }
    }
    
    /**
     * @notice Aggregate calls and revert if any fail
     * @param calls Array of Call structs
     * @return returnData Array of returned bytes from all calls
     */
    function aggregate3(Call[] memory calls) public returns (bytes[] memory returnData) {
        returnData = new bytes[](calls.length);
        
        for (uint256 i = 0; i < calls.length; i++) {
            (bool success, bytes memory result) = calls[i].target.call(calls[i].callData);
            require(success, "Multicall: call failed");
            returnData[i] = result;
        }
    }
    
    /**
     * @notice Helper to encode function calls for multicall
     * @param targets Array of target contract addresses
     * @param data Array of encoded function calls
     * @return calls Array of Call structs
     */
    function createCalls(address[] memory targets, bytes[] memory data) public pure returns (Call[] memory calls) {
        require(targets.length == data.length, "Multicall: length mismatch");
        
        calls = new Call[](targets.length);
        for (uint256 i = 0; i < targets.length; i++) {
            calls[i] = Call(targets[i], data[i]);
        }
    }
    
    // Helper function to get ETH balance
    function getEthBalance(address addr) public view returns (uint256 balance) {
        balance = addr.balance;
    }
    
    // Helper to get contract code size (for checking if address is contract)
    function getCodeSize(address target) public view returns (uint256 size) {
        assembly {
            size := extcodesize(target)
        }
    }
}

// ERC20 ABI for token balance calls
interface IERC20 {
    function balanceOf(address account) external view returns (uint256);
    function decimals() external view returns (uint8);
}

/**
 * @title TokenMulticall
 * @notice Extension for batch ERC20 token queries
 */
contract TokenMulticall is Multicall {
    
    struct TokenBalance {
        address token;
        address holder;
        uint256 balance;
    }
    
    /**
     * @notice Get multiple token balances in one call
     * @param tokens Array of token addresses
     * @param holders Array of holder addresses
     * @return balances Array of balances
     */
    function getTokenBalances(address[] memory tokens, address[] memory holders) public returns (uint256[] memory balances) {
        require(tokens.length == holders.length, "Length mismatch");
        
        balances = new uint256[](tokens.length);
        Call[] memory calls = new Call[](tokens.length);
        
        // Create balanceOf calls for each token
        for (uint256 i = 0; i < tokens.length; i++) {
            // bytes4(keccak256("balanceOf(address)")) = 0x70a08231
            calls[i] = Call(
                tokens[i],
                abi.encodeWithSelector(0x70a08231, holders[i])
            );
        }
        
        // Execute all calls
        Result[] memory results = aggregate(calls);
        
        // Parse results
        for (uint256 i = 0; i < results.length; i++) {
            if (results[i].success && results[i].returnData.length >= 32) {
                balances[i] = abi.decode(results[i].returnData, (uint256));
            }
        }
    }
    
    /**
     * @notice Get token decimals for multiple tokens
     * @param tokens Array of token addresses
     * @return decimalsArray Array of decimals
     */
    function getTokenDecimals(address[] memory tokens) public returns (uint8[] memory decimalsArray) {
        decimalsArray = new uint8[](tokens.length);
        Call[] memory calls = new Call[](tokens.length);
        
        for (uint256 i = 0; i < tokens.length; i++) {
            // bytes4(keccak256("decimals()")) = 0x313ce567
            calls[i] = Call(
                tokens[i],
                abi.encodeWithSelector(0x313ce567)
            );
        }
        
        Result[] memory results = aggregate(calls);
        
        for (uint256 i = 0; i < results.length; i++) {
            if (results[i].success && results[i].returnData.length >= 32) {
                decimalsArray[i] = abi.decode(results[i].returnData, (uint8));
            } else {
                decimalsArray[i] = 18; // Default to 18 if call fails
            }
        }
    }
}
