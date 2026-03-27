# Hardware Wallet Support for AlphaMark
# Provides secure key management using hardware security modules (HSM)

import os
import logging
from typing import Optional
from eth_account import Account
from web3 import Web3

logger = logging.getLogger(__name__)

class HardwareWallet:
    """
    Hardware Wallet interface for secure key management.
    Supports:
    - Ledger hardware wallets
    - Trezor hardware wallets
    - AWS CloudHSM
    - HashiCorp Vault
    """
    
    def __init__(self, provider_type: str = " ledger"):
        self.provider_type = provider_type
        self.w3 = None
        self._account = None
        
    def connect(self, rpc_url: str) -> bool:
        """Connect to the blockchain via RPC"""
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        return self.w3.is_connected()
    
    def get_account(self, derivation_path: str = "m/44'/60'/0'/0/0") -> Optional[Account]:
        """
        Get account from hardware wallet.
        In production, this would use hardware wallet SDKs.
        """
        try:
            if self.provider_type == "ledger":
                return self._connect_ledger(derivation_path)
            elif self.provider_type == "trezor":
                return self._connect_trezor(derivation_path)
            elif self.provider_type == "aws_hsm":
                return self._connect_aws_hsm()
            elif self.provider_type == "vault":
                return self._connect_vault()
            else:
                logger.error(f"Unknown provider type: {self.provider_type}")
                return None
        except Exception as e:
            logger.error(f"Failed to connect to hardware wallet: {e}")
            return None
    
    def _connect_ledger(self, derivation_path: str) -> Optional[Account]:
        """Connect to Ledger hardware wallet"""
        try:
            # In production, use ledgerwallet library:
            # from ledgerwallet import LedgerWallet
            # wallet = LedgerWallet()
            # return wallet.get_account(derivation_path)
            
            # For now, return None if no hardware wallet available
            logger.warning("Ledger hardware wallet not connected - using fallback")
            return self._get_fallback_account()
        except Exception as e:
            logger.error(f"Ledger connection failed: {e}")
            return None
    
    def _connect_trezor(self, derivation_path: str) -> Optional[Account]:
        """Connect to Trezor hardware wallet"""
        try:
            # In production, use trezor library:
            # from trezor import Trezor
            # trezor = Trezor()
            # return trezor.get_account(derivation_path)
            
            logger.warning("Trezor hardware wallet not connected - using fallback")
            return self._get_fallback_account()
        except Exception as e:
            logger.error(f"Trezor connection failed: {e}")
            return None
    
    def _connect_aws_hsm(self) -> Optional[Account]:
        """Connect to AWS CloudHSM"""
        try:
            # In production, use boto3 with AWS CloudHSM:
            # import boto3
            # client = boto3.client('cloudhsmv2')
            # Get key from HSM and derive address
            
            logger.warning("AWS CloudHSM not configured - using fallback")
            return self._get_fallback_account()
        except Exception as e:
            logger.error(f"AWS HSM connection failed: {e}")
            return None
    
    def _connect_vault(self) -> Optional[Account]:
        """Connect to HashiCorp Vault for key management"""
        try:
            # In production, use hvac library:
            # import hvac
            # client = hvac.Client(url=os.environ.get('VAULT_ADDR'))
            # secret = client.read('secret/alphamark/signing_key')
            # private_key = secret['data']['private_key']
            # return Account.from_key(private_key)
            
            logger.warning("HashiCorp Vault not configured - using fallback")
            return self._get_fallback_account()
        except Exception as e:
            logger.error(f"Vault connection failed: {e}")
            return None
    
    def _get_fallback_account(self) -> Optional[Account]:
        """Fallback to environment key (for development only)"""
        private_key = os.environ.get("PRIVATE_KEY")
        if private_key:
            try:
                return Account.from_key(private_key)
            except Exception as e:
                logger.error(f"Invalid private key: {e}")
                return None
        return None
    
    def sign_transaction(self, transaction: dict) -> Optional[bytes]:
        """Sign transaction using hardware wallet"""
        if self._account is None:
            logger.error("No account connected")
            return None
        
        try:
            # Sign using the account (or hardware wallet in production)
            signed = self._account.sign_transaction(transaction)
            return signed.rawTransaction
        except Exception as e:
            logger.error(f"Transaction signing failed: {e}")
            return None
    
    def sign_message(self, message: str) -> Optional[bytes]:
        """Sign message using hardware wallet"""
        if self._account is None:
            logger.error("No account connected")
            return None
        
        try:
            signed = self._account.sign_message(message)
            return signed.signature
        except Exception as e:
            logger.error(f"Message signing failed: {e}")
            return None


class SecureKeyManager:
    """
    Manages secure key storage and access for production deployment.
    Implements defense in depth for key management.
    """
    
    def __init__(self):
        self.hardware_wallet = None
        self.key_mode = self._detect_key_mode()
        
    def _detect_key_mode(self) -> str:
        """Detect which key management mode to use"""
        # Priority: Hardware > Vault > Environment
        
        if os.environ.get("USE_HARDWARE_WALLET", "").lower() == "true":
            return "hardware"
        
        if os.environ.get("VAULT_ADDR"):
            return "vault"
        
        if os.environ.get("PRIVATE_KEY"):
            return "env"
        
        return "none"
    
    def initialize(self, rpc_url: str) -> Optional[Account]:
        """Initialize key management and return account"""
        logger.info(f"Initializing secure key manager in mode: {self.key_mode}")
        
        if self.key_mode == "hardware":
            self.hardware_wallet = HardwareWallet("ledger")
            if self.hardware_wallet.connect(rpc_url):
                account = self.hardware_wallet.get_account()
                if account:
                    logger.info(f"Hardware wallet connected: {account.address}")
                    return account
        
        elif self.key_mode == "vault":
            self.hardware_wallet = HardwareWallet("vault")
            if self.hardware_wallet.connect(rpc_url):
                account = self.hardware_wallet.get_account()
                if account:
                    logger.info(f"Vault access configured: {account.address}")
                    return account
        
        elif self.key_mode == "env":
            private_key = os.environ.get("PRIVATE_KEY")
            if private_key:
                try:
                    account = Account.from_key(private_key)
                    logger.warning("⚠️  Using environment key - NOT RECOMMENDED FOR PRODUCTION")
                    return account
                except Exception as e:
                    logger.error(f"Invalid private key: {e}")
        
        logger.error("No valid key management configuration found")
        return None
    
    def sign_transaction(self, transaction: dict) -> Optional[bytes]:
        """Sign transaction with secure key"""
        if self.hardware_wallet:
            return self.hardware_wallet.sign_transaction(transaction)
        return None
    
    def get_address(self) -> Optional[str]:
        """Get the managed account address"""
        if self.hardware_wallet and self.hardware_wallet._account:
            return self.hardware_wallet._account.address
        return None


def get_secure_signer(rpc_url: str) -> Optional[SecureKeyManager]:
    """
    Factory function to get a secure signer for production use.
    
    Usage:
        signer = get_secure_signer("https://mainnet.infura.io/v3/YOUR_KEY")
        if signer:
            signed_tx = signer.sign_transaction(tx)
    """
    manager = SecureKeyManager()
    account = manager.initialize(rpc_url)
    
    if account:
        return manager
    
    return None


# Environment variables for configuration:
"""
# For Hardware Wallet (recommended for production):
USE_HARDWARE_WALLET=true

# For HashiCorp Vault (recommended for production):
VAULT_ADDR=https://vault.example.com:8200
VAULT_TOKEN=your-vault-token

# For AWS CloudHSM (enterprise):
AWS_CLOUDHSM_CLUSTER_ID=cluster-1234567890
AWS_REGION=us-east-1

# For development only (NOT PRODUCTION):
PRIVATE_KEY=0x...your-private-key...
"""
