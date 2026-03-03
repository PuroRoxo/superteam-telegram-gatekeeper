"""
Configuration management with Pydantic settings
"""

import os
from typing import List, Optional
from pydantic import BaseSettings, validator
from pydantic_settings import BaseSettings as PydanticBaseSettings

class Settings(PydanticBaseSettings):
    """Application settings with validation"""
    
    # Telegram Configuration
    telegram_bot_token: str
    webhook_url: Optional[str] = None
    webhook_secret: Optional[str] = None
    
    # Solana Configuration
    solana_rpc_url: str = "https://api.mainnet-beta.solana.com"
    solana_network: str = "mainnet-beta"
    
    # Admin Configuration
    admin_user_ids: str
    
    # Token Requirements (Optional)
    required_token_mint: Optional[str] = None
    min_token_balance: float = 1000.0
    
    # NFT Collection Requirements (Optional)
    required_nft_collection: Optional[str] = None
    
    # Database
    database_url: str = "sqlite+aiosqlite:///./data/gatekeeper.db"
    
    # Rate Limiting
    max_verification_attempts: int = 5
    rate_limit_window: int = 3600  # 1 hour
    redis_url: str = "redis://localhost:6379"
    
    # Logging
    log_level: str = "INFO"
    log_file: str = "./logs/gatekeeper.log"
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    
    # Security
    verification_timeout: int = 300  # 5 minutes
    max_message_age: int = 600  # 10 minutes
    
    class Config:
        env_file = ".env"
        case_sensitive = False
    
    @validator('admin_user_ids')
    def parse_admin_ids(cls, v):
        """Parse comma-separated admin IDs into list of integers"""
        try:
            return [int(uid.strip()) for uid in v.split(',') if uid.strip()]
        except ValueError:
            raise ValueError("admin_user_ids must be comma-separated integers")
    
    @validator('telegram_bot_token')
    def validate_bot_token(cls, v):
        """Validate Telegram bot token format"""
        if not v or ':' not in v:
            raise ValueError("Invalid Telegram bot token format")
        return v
    
    @validator('solana_rpc_url')
    def validate_rpc_url(cls, v):
        """Validate RPC URL format"""
        if not v.startswith(('http://', 'https://')):
            raise ValueError("RPC URL must start with http:// or https://")
        return v
    
    @validator('required_token_mint', 'required_nft_collection')
    def validate_base58_address(cls, v):
        """Validate Solana addresses are valid base58"""
        if v:
            try:
                import base58
                decoded = base58.b58decode(v)
                if len(decoded) != 32:
                    raise ValueError("Invalid Solana address length")
            except Exception:
                raise ValueError("Invalid base58 address format")
        return v

# Global settings instance
settings = Settings()