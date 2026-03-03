"""
Database initialization script.
Creates tables and sets up initial data.
"""

import asyncio
import sys
from pathlib import Path

# Add src to Python path
sys.path.append(str(Path(__file__).parent.parent))

from config.settings import settings
from database.connection import DatabaseManager, Base
from database.models import User, VerificationRequirement, VerificationSession, AuditLog
from utils.logging_config import setup_logging

logger = setup_logging()


async def init_database():
    """Initialize database tables and setup initial data."""
    try:
        db_manager = DatabaseManager()
        await db_manager.initialize()
        
        # Create all tables
        async with db_manager.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("Database tables created successfully")
        
        # Add initial data if needed
        async with db_manager.get_session() as session:
            # Add default verification requirements here if needed
            pass
        
        await db_manager.close()
        logger.info("Database initialization completed")
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(init_database())