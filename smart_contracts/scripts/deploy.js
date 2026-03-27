const hre = require("hardhat");

async function main() {
  // For standalone arbitrage (no Aave dependency), we use treasury address
  // The contract can receive ETH/tokens directly and execute arbitrage
  const TREASURY_ADDRESS = "0x0000000000000000000000000000000000000001"; // Replace with real treasury
  
  const networkName = hre.network.name;
  const { ethers } = hre;
  
  // Explicitly check for signers to prevent "ENS resolution" errors
  const signers = await ethers.getSigners();
  const deployer = signers[0];

  if (!deployer) {
    throw new Error("❌ No signer available! Check your hardhat.config.js accounts or .env file.");
  }

  console.log(`\n🚀 Deploying FlashLoan to ${networkName}`);
  console.log(`👤 Deployer: ${deployer.address}`);
  console.log(`📜 Treasury: ${TREASURY_ADDRESS}`);

  // Deploy FlashLoan contract with treasury address
  const FlashLoan = await hre.ethers.getContractFactory("FlashLoan");
  const flashLoan = await FlashLoan.deploy(TREASURY_ADDRESS);

  await flashLoan.waitForDeployment();

  const address = await flashLoan.getAddress();
  
  console.log("\n✅ FlashLoan deployed to:", address);
  console.log(`\n💡 Update .env: FLASHLOAN_CONTRACT_ADDRESS=${address}`);
  console.log(`\n📍 Update contracts.json → "flashloan_address": "${address}"`);

  // Verify (if Etherscan API configured)
  if (hre.network.config.chainId !== 31337 && hre.network.config.chainId !== 1337) {
    console.log("\n🔍 Verifying on block explorer...");
    await hre.run("verify:verify", {
      address: address,
      constructorArguments: [TREASURY_ADDRESS],
    });
  }
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
