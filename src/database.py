"""
Database models and operations using SQLAlchemy with async support
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional, List
import uuid

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime, Boolean, Text, Float, Index
from sqlalchemy.dialects.sqlite import insert
import structlog

from config import settings

logger = structlog.get_logger(__name__)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    wallet_address: Mapped[Optional[str]] = mapped_column(String(44), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_whitelisted: Mapped[bool] = mapped_column(Boolean, default=False)
    is_blacklisted: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Add indexes for performance
    __table_args__ = (
        Index('ix_users_telegram_id', 'telegram_id'),
        Index('ix_users_wallet_address', 'wallet_address'),
        Index('ix_users_verified', 'is_verified'),
    )

class VerificationSession(Base):
    __tablename__ = "verification_sessions"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    telegram_id: Mapped[int] = mapped_column(Integer, nullable=False)
    challenge_message: Mapped[str] = mapped_column(Text, nullable=False)
    wallet_address: Mapped[Optional[str]] = mapped_column(String(44), nullable=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    
    __table_args__ = (
        Index('ix_sessions_telegram_id', 'telegram_id'),
        Index('ix_sessions_expires', 'expires_at'),
    )

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    admin_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    
    __table_args__ = (
        Index('ix_logs_telegram_id', 'telegram_id'),
        Index('ix_logs_action', 'action'),
        Index('ix_logs_created', 'created_at'),
    )

# Database engine and session
engine = None
SessionLocal = None

async def init_database():
    """Initialize database connection and create tables"""
    global engine, SessionLocal
    
    try:
        engine = create_async_engine(
            settings.database_url,
            echo=settings.log_level == "DEBUG",
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        
        SessionLocal = async_sessionmaker(
            engine, 
            class_=AsyncSession, 
            expire_on_commit=False
        )
        
        # Create tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("Database initialized successfully")
        
    except Exception as e:
        logger.error("Database initialization failed", error=str(e))
        raise

async def close_database():
    """Close database connections"""
    global engine
    if engine:
        await engine.dispose()
        logger.info("Database connections closed")

async def get_session() -> AsyncSession:
    """Get database session"""
    if not SessionLocal:
        raise RuntimeError("Database not initialized")
    
    async with SessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error("Database session error", error=str(e))
            raise
        finally:
            await session.close()

# Database operations
class DatabaseOperations:
    """Database operations with proper error handling"""
    
    @staticmethod
    async def get_user_by_telegram_id(telegram_id: int) -> Optional[User]:
        """Get user by Telegram ID"""
        async with SessionLocal() as session:
            try:
                from sqlalchemy import select
                result = await session.execute(
                    select(User).where(User.telegram_id == telegram_id)
                )
                return result.scalar_one_or_none()
            except Exception as e:
                logger.error("Failed to get user", telegram_id=telegram_id, error=str(e))
                return None
    
    @staticmethod
    async def create_or_update_user(
        telegram_id: int, 
        username: Optional[str] = None,
        wallet_address: Optional[str] = None,
        **kwargs
    ) -> Optional[User]:
        """Create or update user"""
        async with SessionLocal() as session:
            try:
                # Use upsert for SQLite
                stmt = insert(User).values(
                    telegram_id=telegram_id,
                    username=username,
                    wallet_address=wallet_address,
                    updated_at=datetime.utcnow(),
                    **kwargs
                )
                
                # On conflict, update all provided fields
                update_dict = {
                    "username": stmt.excluded.username,
                    "updated_at": stmt.excluded.updated_at,
                }
                if wallet_address:
                    update_dict["wallet_address"] = stmt.excluded.wallet_address
                
                update_dict.update(kwargs)
                
                stmt = stmt.on_conflict_do_update(
                    index_elements=[User.telegram_id],
                    set_=update_dict
                )
                
                await session.execute(stmt)
                await session.commit()
                
                # Return updated user
                return await DatabaseOperations.get_user_by_telegram_id(telegram_id)
                
            except Exception as e:
                await session.rollback()
                logger.error("Failed to create/update user", telegram_id=telegram_id, error=str(e))
                return None
    
    @staticmethod
    async def create_verification_session(
        telegram_id: int, 
        challenge_message: str, 
        expires_at: datetime
    ) -> Optional[str]:
        """Create verification session"""
        async with SessionLocal() as session:
            try:
                session_id = str(uuid.uuid4())
                verification_session = VerificationSession(
                    id=session_id,
                    telegram_id=telegram_id,
                    challenge_message=challenge_message,
                    expires_at=expires_at
                )
                
                session.add(verification_session)
                await session.commit()
                
                return session_id
                
            except Exception as e:
                await session.rollback()
                logger.error("Failed to create verification session", telegram_id=telegram_id, error=str(e))
                return None
    
    @staticmethod
    async def get_verification_session(session_id: str) -> Optional[VerificationSession]:
        """Get verification session"""
        async with SessionLocal() as session:
            try:
                from sqlalchemy import select
                result = await session.execute(
                    select(VerificationSession).where(
                        VerificationSession.id == session_id,
                        VerificationSession.expires_at > datetime.utcnow(),
                        VerificationSession.is_completed == False
                    )
                )
                return result.scalar_one_or_none()
            except Exception as e:
                logger.error("Failed to get verification session", session_id=session_id, error=str(e))
                return None
    
    @staticmethod
    async def complete_verification_session(session_id: str, wallet_address: str) -> bool:
        """Complete verification session"""
        async with SessionLocal() as session:
            try:
                from sqlalchemy import select, update
                
                # Update session
                await session.execute(
                    update(VerificationSession).where(
                        VerificationSession.id == session_id
                    ).values(
                        is_completed=True,
                        wallet_address=wallet_address
                    )
                )
                
                await session.commit()
                return True
                
            except Exception as e:
                await session.rollback()
                logger.error("Failed to complete verification session", session_id=session_id, error=str(e))
                return False
    
    @staticmethod
    async def log_audit_event(
        telegram_id: int,
        action: str,
        details: Optional[str] = None,
        admin_id: Optional[int] = None,
        ip_address: Optional[str] = None
    ) -> bool:
        """Log audit event"""
        async with SessionLocal() as session:
            try:
                log_entry = AuditLog(
                    telegram_id=telegram_id,
                    action=action,
                    details=details,
                    admin_id=admin_id,
                    ip_address=ip_address
                )
                
                session.add(log_entry)
                await session.commit()
                return True
                
            except Exception as e:
                await session.rollback()
                logger.error("Failed to log audit event", telegram_id=telegram_id, action=action, error=str(e))
                return False
    
    @staticmethod
    async def get_stats() -> dict:
        """Get bot statistics"""
        async with SessionLocal() as session:
            try:
                from sqlalchemy import select, func
                
                # Total users
                total_users = await session.scalar(select(func.count(User.id)))
                
                # Verified users
                verified_users = await session.scalar(
                    select(func.count(User.id)).where(User.is_verified == True)
                )
                
                # Pending verifications
                pending_verifications = await session.scalar(
                    select(func.count(VerificationSession.id)).where(
                        VerificationSession.is_completed == False,
                        VerificationSession.expires_at > datetime.utcnow()
                    )
                )
                
                # Whitelisted users
                whitelisted_users = await session.scalar(
                    select(func.count(User.id)).where(User.is_whitelisted == True)
                )
                
                # Blacklisted users
                blacklisted_users = await session.scalar(
                    select(func.count(User.id)).where(User.is_blacklisted == True)
                )
                
                return {
                    "total_users": total_users or 0,
                    "verified_users": verified_users or 0,
                    "pending_verifications": pending_verifications or 0,
                    "whitelisted_users": whitelisted_users or 0,
                    "blacklisted_users": blacklisted_users or 0,
                }
                
            except Exception as e:
                logger.error("Failed to get stats", error=str(e))
                return {}

# Cleanup expired sessions periodically
async def cleanup_expired_sessions():
    """Cleanup expired verification sessions"""
    async with SessionLocal() as session:
        try:
            from sqlalchemy import delete
            result = await session.execute(
                delete(VerificationSession).where(
                    VerificationSession.expires_at < datetime.utcnow()
                )
            )
            await session.commit()
            
            if result.rowcount > 0:
                logger.info("Cleaned up expired sessions", count=result.rowcount)
                
        except Exception as e:
            await session.rollback()
            logger.error("Failed to cleanup expired sessions", error=str(e))

if __name__ == "__main__":
    # Initialize database tables
    async def main():
        await init_database()
        print("Database initialized successfully!")
    
    asyncio.run(main())