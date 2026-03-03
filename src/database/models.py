"""
SQLAlchemy models for the Superteam Telegram bot.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON, BigInteger, Numeric
from sqlalchemy.sql import func
from enum import Enum as PyEnum

from .connection import Base


class VerificationStatus(PyEnum):
    """Verification status enumeration."""
    PENDING = "pending"
    VERIFIED = "verified" 
    REJECTED = "rejected"
    EXPIRED = "expired"


class User(Base):
    """User model for storing Telegram user information."""
    
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    
    # Verification data
    wallet_address = Column(String(44), nullable=True, index=True)
    verification_status = Column(String(20), default=VerificationStatus.PENDING.value, nullable=False)
    verification_attempts = Column(Integer, default=0, nullable=False)
    last_verification_attempt = Column(DateTime(timezone=True), nullable=True)
    
    # Status tracking
    is_banned = Column(Boolean, default=False, nullable=False)
    ban_reason = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<User(telegram_id={self.telegram_id}, status={self.verification_status})>"


class VerificationRequirement(Base):
    """Model for storing verification requirements."""
    
    __tablename__ = 'verification_requirements'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    requirement_type = Column(String(20), nullable=False)  # 'token', 'nft', 'transaction'
    
    # Token requirements
    token_mint = Column(String(44), nullable=True)
    minimum_amount = Column(Numeric(precision=20, scale=9), nullable=True)
    
    # NFT requirements  
    collection_address = Column(String(44), nullable=True)
    
    # Transaction requirements
    min_transaction_count = Column(Integer, nullable=True)
    min_transaction_volume = Column(Numeric(precision=20, scale=9), nullable=True)
    
    # Configuration
    is_active = Column(Boolean, default=True, nullable=False)
    description = Column(Text, nullable=True)
    
    # Metadata
    created_by = Column(BigInteger, nullable=False)  # Admin telegram_id
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<VerificationRequirement(type={self.requirement_type}, active={self.is_active})>"


class VerificationSession(Base):
    """Model for tracking verification sessions."""
    
    __tablename__ = 'verification_sessions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, nullable=False, index=True)
    
    # Session data
    nonce = Column(String(64), nullable=False, unique=True)
    wallet_address = Column(String(44), nullable=True)
    signature = Column(String(128), nullable=True)
    
    # Status tracking
    status = Column(String(20), default=VerificationStatus.PENDING.value, nullable=False)
    error_message = Column(Text, nullable=True)
    verification_data = Column(JSON, nullable=True)  # Store verification results
    
    # Timestamps
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<VerificationSession(telegram_id={self.telegram_id}, status={self.status})>"


class AuditLog(Base):
    """Model for audit logging."""
    
    __tablename__ = 'audit_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Event data
    event_type = Column(String(50), nullable=False, index=True)
    telegram_id = Column(BigInteger, nullable=True, index=True)
    admin_id = Column(BigInteger, nullable=True)
    
    # Event details
    description = Column(Text, nullable=False)
    metadata = Column(JSON, nullable=True)
    
    # Tracking
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    user_agent = Column(Text, nullable=True)
    
    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<AuditLog(event_type={self.event_type}, telegram_id={self.telegram_id})>"