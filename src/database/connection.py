"""
Database connection and management for PostgreSQL.
"""

from typing import Optional
import asyncio
import asyncpg
import structlog
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text

from config.settings import settings

logger = structlog.get_logger(__name__)

Base = declarative_base()


class DatabaseManager:
    """Manages database connections and sessions."""
    
    def __init__(self):
        self.engine = None
        self.session_factory: Optional[async_sessionmaker[AsyncSession]] = None
        self._pool: Optional[asyncpg.Pool] = None
    
    async def initialize(self):
        """Initialize database engine and connection pool."""
        try:
            # Create SQLAlchemy engine
            self.engine = create_async_engine(
                settings.database_url.replace("postgresql://", "postgresql+asyncpg://"),
                echo=settings.log_level == "DEBUG",
                pool_size=20,
                max_overflow=30,
                pool_pre_ping=True,
                pool_recycle=3600,
            )
            
            # Create session factory
            self.session_factory = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Test connection
            async with self.engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            
            logger.info("Database initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    async def get_session(self) -> AsyncSession:
        """Get a database session."""
        if not self.session_factory:
            raise RuntimeError("Database not initialized")
        
        return self.session_factory()
    
    async def close(self):
        """Close database connections."""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connections closed")
    
    async def health_check(self) -> bool:
        """Check database connectivity."""
        try:
            async with self.engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False