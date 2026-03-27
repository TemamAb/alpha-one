const { expect } = require("chai");
const { ethers, network } = require("hardhat");

describe("FlashLoan", function () {
  let flashLoan, poolProvider, mockPool, mockToken, owner, addr1;
  
  beforeEach(async function () {
    [owner, addr1] = await ethers.getSigners();
    
    // Deploy mocks
    const MockPoolProvider = await ethers.getContractFactory("MockPoolAddressesProvider");
    poolProvider = await MockPoolProvider.deploy();
    
    const MockPool = await ethers.getContractFactory("MockAavePool");
    mockPool = await MockPool.deploy();
    
    const MockERC20 = await ethers.getContractFactory("MockERC20");
    mockToken = await MockERC20.deploy("MockUSDC", "USDC", 6);
    
    // Fund contract
    await mockToken.mint(addr1.address, ethers.parseUnits("1000000", 6));
    
    // Deploy FlashLoan
    const FlashLoan = await ethers.getContractFactory("FlashLoan");
    flashLoan = await FlashLoan.deploy(poolProvider.target);
  });

  describe("Deployment", function () {
    it("Should set owner to deployer", async function () {
      expect(await flashLoan.owner()).to.equal(owner.address);
    });
  });

  describe("FlashLoan Execution", function () {
    it("Should execute flashloan and repay", async function () {
      const amount = ethers.parseUnits("1000", 6);
      
      // Fund pool for repayment
      await mockToken.mint(flashLoan.target, amount * 2);
      
      await expect(flashLoan.connect(addr1).startFlashLoan(
        mockPool.target,
        [mockToken.target],
        [amount],
        "0x"
      )).to.emit(flashLoan, "FlashLoanExecuted");
      
      // Check profit withdrawn
      expect(await mockToken.balanceOf(addr1.address)).to.be.gt(0);
    });
    
    it("Should revert if not owner", async function () {
      await expect(
        flashLoan.connect(addr1).startFlashLoan(mockPool.target, [], [], "0x")
      ).to.be.revertedWith("Not owner");
    });
    
    it("Should handle repayment failure", async function () {
      const amount = ethers.parseUnits("1000", 6);
      
      await expect(flashLoan.connect(owner).startFlashLoan(
        mockPool.target,
        [mockToken.target],
        [amount],
        "0x"
      )).to.be.revertedWith("Repayment failed"); // Mock pool reverts
    });
  });

  describe("Withdraw", function () {
    it("Should allow owner to withdraw profits", async function () {
      await mockToken.mint(flashLoan.target, ethers.parseUnits("500", 6));
      
      const preBalance = await mockToken.balanceOf(owner.address);
      await flashLoan.withdraw(mockToken.target);
      const postBalance = await mockToken.balanceOf(owner.address);
      
      expect(postBalance).to.equal(preBalance + ethers.parseUnits("500", 6));
    });
  });
});
