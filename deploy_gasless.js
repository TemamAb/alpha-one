const fs = require("fs");
const axios = require("axios");
const { ethers } = require("ethers");

// Load compiled contract ABI + bytecode
const compiled = JSON.parse(fs.readFileSync("smart_contracts/contracts/CrossChainFlashLoan.json"));
const abi = compiled.abi;
const bytecode = compiled.bytecode;

// Local wallet for signing meta-transaction
const privateKey = process.env.PRIVATE_KEY;
if(!privateKey) {
    console.error("Set PRIVATE_KEY in environment variables");
    process.exit(1);
}
const wallet = new ethers.Wallet(privateKey);

// Prepare deployment transaction
const factory = new ethers.ContractFactory(abi, bytecode, wallet);
const deployTx = factory.getDeployTransaction("0xPoolAddressProvider"); // replace with actual pool provider

async function signAndSendGasless() {
    try {
        const signedTx = await wallet.signTransaction(deployTx);

        // Send signed transaction to Pilmico relayer
        const pilmicoApiKey = process.env.PILMICO_API_KEY;
        if(!pilmicoApiKey) {
            console.error("Set PILMICO_API_KEY in environment variables");
            process.exit(1);
        }

        const response = await axios.post(
            "http://localhost:3000/api/relay",  // Local cloud relay endpoint
            { rawTx: signedTx },
            { headers: { "Authorization": `Bearer ${pilmicoApiKey}` } }
        );

        console.log("Gasless deployment response:", response.data);
    } catch (err) {
        console.error(err);
    }
}

signAndSendGasless();
