"""
Solana blockchain interaction with proper error handling and validation
"""

import base58
import time
from typing import Optional, Dict, Any, List
from datetime import datetime

import httpx
import structlog
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solana.rpc.types import TokenAccountOpts
from solana.publickey import PublicKey
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

from config import settings

logger = structlog.get_logger(__name__)

class SolanaClient:
    """Solana RPC client with comprehensive validation"""
    
    def __init__(self):
        self.rpc_client = AsyncClient(settings.solana_rpc_url)
        self.http_client = httpx.AsyncClient(timeout=30.0)
    
    async def close(self):
        """Close client connections"""
        await self.rpc_client.close()
        await self.http_client.aclose()
    
    def validate_wallet_address(self, address: str) -> bool:
        """Validate Solana wallet address format"""
        try:
            public_key = PublicKey(address)
            # Additional validation - should be 32 bytes when decoded
            decoded = base58.b58decode(address)
            return len(decoded) == 32
        except Exception as e:
            logger.debug("Invalid wallet address", address=address, error=str(e))
            return False
    
    def verify_message_signature(
        self, 
        message: str, 
        signature: str, 
        wallet_address: str
    ) -> bool:
        """
        Verify ed25519 signature for message
        
        SECURITY NOTE: This validates that the wallet holder signed the message
        """
        try:
            # Validate inputs
            if not self.validate_wallet_address(wallet_address):
                logger.warning("Invalid wallet address format", address=wallet_address)
                return False
            
            # Decode signature and message
            try:
                signature_bytes = base58.b58decode(signature)
                if len(signature_bytes) != 64:
                    logger.warning("Invalid signature length", length=len(signature_bytes))
                    return False
                    
                message_bytes = message.encode('utf-8')
                wallet_bytes = base58.b58decode(wallet_address)
                
            except Exception as e:
                logger.warning("Failed to decode signature or address", error=str(e))
                return False
            
            # Verify signature using PyNaCl
            try:
                verify_key = VerifyKey(wallet_bytes)
                verify_key.verify(message_bytes, signature_bytes)
                return True
                
            except BadSignatureError:
                logger.warning("Signature verification failed", wallet=wallet_address)
                return False
                
        except Exception as e:
            logger.error("Signature verification error", error=str(e), wallet=wallet_address)
            return False
    
    def generate_verification_message(self, telegram_id: int, timestamp: Optional[int] = None) -> str:
        """
        Generate unique verification message
        
        SECURITY NOTE: Includes timestamp to prevent replay attacks
        """
        if timestamp is None:
            timestamp = int(time.time())
        
        return (
            f"Verify wallet ownership for Superteam Telegram access\n"
            f"Telegram ID: {telegram_id}\n"
            f"Timestamp: {timestamp}\n"
            f"Action: wallet_verification\n"
            f"Note: This signature is only valid for 10 minutes"
        )
    
    def validate_message_timestamp(self, message: str, max_age_seconds: int = None) -> bool:
        """
        Validate message timestamp to prevent replay attacks
        
        SECURITY CRITICAL: Always check message age in production
        """
        if max_age_seconds is None:
            max_age_seconds = settings.max_message_age
            
        try:
            # Extract timestamp from message
            lines = message.split('\n')
            timestamp_line = next((line for line in lines if line.startswith('Timestamp:')), None)
            
            if not timestamp_line:
                logger.warning("No timestamp found in message")
                return False
            
            timestamp = int(timestamp_line.split(':')[1].strip())
            current_time = int(time.time())
            age = current_time - timestamp
            
            if age > max_age_seconds:
                logger.warning("Message too old", age=age, max_age=max_age_seconds)
                return False
                
            if age < -60:  # Allow 1 minute clock skew
                logger.warning("Message from future", age=age)
                return False
            
            return True
            
        except Exception as e:
            logger.error("Failed to validate message timestamp", error=str(e))
            return False
    
    async def get_token_balance(
        self, 
        wallet_address: str, 
        token_mint: str
    ) -> Optional[float]:
        """Get SPL token balance for wallet"""
        try:
            if not self.validate_wallet_address(wallet_address):
                return None
            
            wallet_pubkey = PublicKey(wallet_address)
            mint_pubkey = PublicKey(token_mint)
            
            # Get token accounts for wallet
            response = await self.rpc_client.get_token_accounts_by_owner(
                wallet_pubkey,
                TokenAccountOpts(mint=mint_pubkey),
                commitment=Confirmed
            )
            
            if not response.value:
                logger.debug("No token accounts found", wallet=wallet_address, mint=token_mint)
                return 0.0
            
            total_balance = 0.0
            for account in response.value:
                account_data = account.account.data.parsed['info']
                balance = float(account_data['tokenAmount']['uiAmount'])
                total_balance += balance
            
            logger.debug("Token balance retrieved", 
                        wallet=wallet_address, 
                        mint=token_mint, 
                        balance=total_balance)
            return total_balance
            
        except Exception as e:
            logger.error("Failed to get token balance", 
                        wallet=wallet_address, 
                        mint=token_mint, 
                        error=str(e))
            return None
    
    async def check_nft_ownership(
        self, 
        wallet_address: str, 
        collection_address: str
    ) -> bool:
        """Check if wallet owns NFTs from specific collection"""
        try:
            if not self.validate_wallet_address(wallet_address):
                return False
            
            wallet_pubkey = PublicKey(wallet_address)
            
            # Get all token accounts for wallet
            response = await self.rpc_client.get_token_accounts_by_owner(
                wallet_pubkey,
                TokenAccountOpts(program_id=PublicKey("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")),
                commitment=Confirmed
            )
            
            if not response.value:
                return False
            
            # Check each NFT (balance = 1, decimals = 0)
            for account in response.value:
                try:
                    account_data = account.account.data.parsed['info']
                    if (account_data['tokenAmount']['decimals'] == 0 and 
                        float(account_data['tokenAmount']['uiAmount']) == 1.0):
                        
                        # Get NFT metadata to check collection
                        mint_address = account_data['mint']
                        nft_metadata = await self.get_nft_metadata(mint_address)
                        
                        if nft_metadata and nft_metadata.get('collection') == collection_address:
                            logger.debug("NFT found in collection", 
                                        wallet=wallet_address, 
                                        collection=collection_address,
                                        mint=mint_address)
                            return True
                            
                except Exception as e:
                    logger.debug("Error checking NFT", mint=account_data.get('mint'), error=str(e))
                    continue
            
            return False
            
        except Exception as e:
            logger.error("Failed to check NFT ownership", 
                        wallet=wallet_address, 
                        collection=collection_address, 
                        error=str(e))
            return False
    
    async def get_nft_metadata(self, mint_address: str) -> Optional[Dict[str, Any]]:
        """Get NFT metadata from mint address"""
        try:
            # Use a metadata service or on-chain program
            # This is a simplified version - in production, use Metaplex metadata program
            async with self.http_client.get(f"https://api.metaplex.solana.com/nft/{mint_address}") as response:
                if response.status_code == 200:
                    return response.json()
        except Exception as e:
            logger.debug("Failed to get NFT metadata", mint=mint_address, error=str(e))
        
        return None
    
    async def verify_jupiter_trading_history(
        self, 
        wallet_address: str, 
        min_trades: int = 1,
        days_back: int = 30
    ) -> bool:
        """
        Check Jupiter trading history for wallet
        
        NOTE: This requires Jupiter API integration
        """
        try:
            if not self.validate_wallet_address(wallet_address):
                return False
            
            # Jupiter API call (requires API key in production)
            url = f"https://api.jup.ag/stats/wallet/{wallet_address}"
            
            async with self.http_client.get(url, timeout=10.0) as response:
                if response.status_code != 200:
                    logger.debug("Jupiter API request failed", 
                                wallet=wallet_address, 
                                status=response.status_code)
                    return False
                
                data = response.json()
                trade_count = data.get('total_trades', 0)
                
                logger.debug("Jupiter trading history", 
                           wallet=wallet_address, 
                           trades=trade_count)
                
                return trade_count >= min_trades
                
        except Exception as e:
            logger.error("Failed to check Jupiter trading history", 
                        wallet=wallet_address, 
                        error=str(e))
            return False
    
    async def validate_wallet_requirements(self, wallet_address: str) -> Dict[str, bool]:
        """
        Validate all wallet requirements
        Returns dict with requirement results
        """
        results = {
            'valid_address': False,
            'token_balance_ok': True,  # Default true if no token required
            'nft_ownership_ok': True,  # Default true if no NFT required
            'trading_history_ok': True,  # Default true if no trading required
        }
        
        try:
            # Basic address validation
            results['valid_address'] = self.validate_wallet_address(wallet_address)
            if not results['valid_address']:
                return results
            
            # Check token balance requirement
            if settings.required_token_mint:
                balance = await self.get_token_balance(wallet_address, settings.required_token_mint)
                results['token_balance_ok'] = (balance is not None and 
                                             balance >= settings.min_token_balance)
            
            # Check NFT ownership requirement  
            if settings.required_nft_collection:
                results['nft_ownership_ok'] = await self.check_nft_ownership(
                    wallet_address, 
                    settings.required_nft_collection
                )
            
            # Check trading history (optional)
            # results['trading_history_ok'] = await self.verify_jupiter_trading_history(wallet_address)
            
            logger.info("Wallet validation completed", 
                       wallet=wallet_address, 
                       results=results)
            
        except Exception as e:
            logger.error("Wallet validation failed", 
                        wallet=wallet_address, 
                        error=str(e))
        
        return results
    
    async def health_check(self) -> bool:
        """Check RPC endpoint health"""
        try:
            response = await self.rpc_client.get_health()
            return response.value == "ok"
        except Exception as e:
            logger.error("RPC health check failed", error=str(e))
            return False

# Global client instance
solana_client = SolanaClient()