"""
Configuration settings for the Superteam Telegram Gatekeeper Bot.
Uses pydantic-settings for type-safe environment variable handling.
"""

from typing import List, Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration with validation."""
    
    # Telegram Configuration
    telegram_bot_token: str = Field(..., description="Telegram bot token from @BotFather")
    webhook_url: Optional[str] = Field(None, description="Webhook URL for production")
    webhook_secret: Optional[str] = Field(None, description="Webhook secret token")
    
    # Solana Configuration
    solana_rpc_url: str = Field(
        default="https://api.mainnet-beta.solana.com",
        description="Solana RPC endpoint URL"
    )
    solana_commitment: str = Field(default="confirmed", description="Solana commitment level")
    
    # Database Configuration
    database_url: str = Field(..., description="PostgreSQL connection string")
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis connection string")
    
    # Bot Configuration
    admin_user_ids: str = Field(..., description="Comma-separated admin user IDs")
    verification_timeout_seconds: int = Field(default=300, description="Verification timeout in seconds")
    rate_limit_requests: int = Field(default=10, description="Rate limit requests per window")
    rate_limit_window_seconds: int = Field(default=60, description="Rate limit window in seconds")
    
    # Logging Configuration
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format: json or text")
    
    # Security Configuration
    max_verification_attempts: int = Field(default=3, description="Max verification attempts per user")
    signature_message_template: str = Field(
        default="Superteam verification: {nonce}",
        description="Template for signature verification message"
    )
    
    @validator('admin_user_ids')
    def parse_admin_ids(cls, v):
        """Parse comma-separated admin IDs into a list of integers."""
        try:
            return [int(user_id.strip()) for user_id in v.split(',') if user_id.strip()]
        except ValueError as e:
            raise ValueError(f"Invalid admin user ID format: {e}")
    
    @validator('solana_commitment')
    def validate_commitment(cls, v):
        """Validate Solana commitment level."""
        valid_commitments = ['processed', 'confirmed', 'finalized']
        if v not in valid_commitments:
            raise ValueError(f"Invalid commitment level. Must be one of: {valid_commitments}")
        return v
    
    @validator('log_level')
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level. Must be one of: {valid_levels}")
        return v.upper()
    
    def get_admin_ids(self) -> List[int]:
        """Get list of admin user IDs."""
        return self.admin_user_ids
    
    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        case_sensitive = False


# Global settings instance
settings = Settings()