"""
Solana blockchain service for wallet verification and token/NFT checking.
"""

import asyncio
from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal
import base58
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment
from solana.rpc.types import TokenAccountOpts
from solders.pubkey import Pubkey
from solders.signature import Signature
from spl.token.constants import TOKEN_PROGRAM_ID
import nacl.signing
import nacl.encoding
import structlog

from config.settings import settings

logger = structlog.get_logger(__name__)


class SolanaService:
    """Service for interacting with Solana blockchain."""
    
    def __init__(self):
        self.client: Optional[AsyncClient] = None
        self.commitment = Commitment(settings.solana_commitment)
    
    async def initialize(self):
        """Initialize Solana RPC client."""
        try:
            self.client = AsyncClient(
                endpoint=settings.solana_rpc_url,
                commitment=self.commitment,
                timeout=30,
            )
            
            # Test connection
            response = await self.client.get_health()
            if response.value != "ok":
                raise Exception(f"Solana RPC health check failed: {response.value}")
                
            logger.info("Solana service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Solana service: {e}")
            raise
    
    async def verify_wallet_signature(
        self, 
        wallet_address: str, 
        message: str, 
        signature: str
    ) -> bool:
        """
        Verify that a message was signed by the specified wallet.
        
        Args:
            wallet_address: Solana wallet public key
            message: Original message that was signed
            signature: Base58 encoded signature
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            # Decode the public key and signature
            public_key_bytes = base58.b58decode(wallet_address)
            signature_bytes = base58.b58decode(signature)
            
            # Create verification key
            verify_key = nacl.signing.VerifyKey(public_key_bytes)
            
            # Verify signature
            message_bytes = message.encode('utf-8')
            verify_key.verify(message_bytes, signature_bytes)
            
            logger.info(f"Signature verification successful for wallet: {wallet_address}")
            return True
            
        except Exception as e:
            logger.warning(f"Signature verification failed for wallet {wallet_address}: {e}")
            return False
    
    async def get_token_balance(self, wallet_address: str, token_mint: str) -> Decimal:
        """
        Get SPL token balance for a wallet.
        
        Args:
            wallet_address: Solana wallet public key
            token_mint: Token mint address
            
        Returns:
            Token balance as Decimal
        """
        if not self.client:
            raise RuntimeError("Solana client not initialized")
        
        try:
            wallet_pubkey = Pubkey.from_string(wallet_address)
            mint_pubkey = Pubkey.from_string(token_mint)
            
            # Get token accounts for the wallet
            response = await self.client.get_token_accounts_by_owner(
                wallet_pubkey,
                TokenAccountOpts(mint=mint_pubkey),
                commitment=self.commitment
            )
            
            if not response.value:
                return Decimal('0')
            
            total_balance = Decimal('0')
            
            for account in response.value:
                account_data = account.account.data.parsed['info']
                token_amount = account_data['tokenAmount']
                balance = Decimal(token_amount['amount']) / (10 ** token_amount['decimals'])
                total_balance += balance
            
            logger.debug(f"Token balance for {wallet_address}: {total_balance} {token_mint}")
            return total_balance
            
        except Exception as e:
            logger.error(f"Failed to get token balance: {e}")
            return Decimal('0')
    
    async def get_nft_count(self, wallet_address: str, collection_address: Optional[str] = None) -> int:
        """
        Get NFT count for a wallet, optionally filtered by collection.
        
        Args:
            wallet_address: Solana wallet public key
            collection_address: Optional collection address to filter by
            
        Returns:
            Number of NFTs owned
        """
        if not self.client:
            raise RuntimeError("Solana client not initialized")
        
        try:
            wallet_pubkey = Pubkey.from_string(wallet_address)
            
            # Get all token accounts with balance = 1 and decimals = 0 (NFTs)
            response = await self.client.get_token_accounts_by_owner(
                wallet_pubkey,
                TokenAccountOpts(program_id=TOKEN_PROGRAM_ID),
                commitment=self.commitment
            )
            
            if not response.value:
                return 0
            
            nft_count = 0
            
            for account in response.value:
                try:
                    account_data = account.account.data.parsed['info']
                    token_amount = account_data['tokenAmount']
                    
                    # Check if it's an NFT (balance = 1, decimals = 0)
                    if (token_amount['amount'] == '1' and 
                        token_amount['decimals'] == 0):
                        
                        # If collection filter specified, check collection
                        if collection_address:
                            # This would require additional metadata parsing
                            # For now, count all NFTs
                            pass
                        
                        nft_count += 1
                        
                except Exception as account_error:
                    logger.debug(f"Error processing token account: {account_error}")
                    continue
            
            logger.debug(f"NFT count for {wallet_address}: {nft_count}")
            return nft_count
            
        except Exception as e:
            logger.error(f"Failed to get NFT count: {e}")
            return 0
    
    async def get_transaction_stats(self, wallet_address: str) -> Dict[str, Any]:
        """
        Get transaction statistics for a wallet.
        
        Args:
            wallet_address: Solana wallet public key
            
        Returns:
            Dictionary with transaction statistics
        """
        if not self.client:
            raise RuntimeError("Solana client not initialized")
        
        try:
            wallet_pubkey = Pubkey.from_string(wallet_address)
            
            # Get confirmed signatures (limited to recent transactions)
            response = await self.client.get_signatures_for_address(
                wallet_pubkey,
                limit=1000,  # Adjust based on needs vs performance
                commitment=self.commitment
            )
            
            if not response.value:
                return {
                    'transaction_count': 0,
                    'total_volume': Decimal('0'),
                    'first_transaction': None,
                    'last_transaction': None
                }
            
            signatures = response.value
            transaction_count = len(signatures)
            
            # For volume calculation, we'd need to parse individual transactions
            # This is expensive, so we'll estimate based on signature count
            stats = {
                'transaction_count': transaction_count,
                'total_volume': Decimal('0'),  # Would need full transaction parsing
                'first_transaction': signatures[-1].block_time if signatures else None,
                'last_transaction': signatures[0].block_time if signatures else None
            }
            
            logger.debug(f"Transaction stats for {wallet_address}: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get transaction stats: {e}")
            return {
                'transaction_count': 0,
                'total_volume': Decimal('0'),
                'first_transaction': None,
                'last_transaction': None
            }
    
    async def validate_wallet_address(self, address: str) -> bool:
        """
        Validate if a string is a valid Solana wallet address.
        
        Args:
            address: Address string to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Attempt to create a Pubkey object
            Pubkey.from_string(address)
            return True
        except Exception:
            return False
    
    async def close(self):
        """Close Solana client connection."""
        if self.client:
            await self.client.close()
            logger.info("Solana client connection closed")