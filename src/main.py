"""
Superteam Telegram Gatekeeper Bot
Main entry point for the bot application.
"""

import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram.ext import CallbackQueryHandler

from config.settings import settings
from handlers.admin import AdminHandler
from handlers.auth import AuthHandler
from handlers.verification import VerificationHandler
from handlers.webhook import WebhookHandler
from database.connection import DatabaseManager
from utils.logging_config import setup_logging
from utils.rate_limiter import RateLimiter

# Setup structured logging
logger = setup_logging()


class SuperteamBot:
    """Main bot class that orchestrates all components."""
    
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.rate_limiter = RateLimiter()
        self.app = None
        
    async def initialize(self):
        """Initialize all bot components."""
        try:
            # Initialize database
            await self.db_manager.initialize()
            logger.info("Database initialized successfully")
            
            # Initialize rate limiter
            await self.rate_limiter.initialize()
            logger.info("Rate limiter initialized successfully")
            
            # Create application
            self.app = Application.builder().token(settings.telegram_bot_token).build()
            
            # Register handlers
            await self._register_handlers()
            logger.info("Handlers registered successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}")
            raise
    
    async def _register_handlers(self):
        """Register all command and message handlers."""
        # Initialize handler classes
        auth_handler = AuthHandler(self.db_manager, self.rate_limiter)
        verification_handler = VerificationHandler(self.db_manager, self.rate_limiter)
        admin_handler = AdminHandler(self.db_manager)
        webhook_handler = WebhookHandler(self.db_manager, self.rate_limiter)
        
        # Command handlers
        self.app.add_handler(CommandHandler("start", auth_handler.start_command))
        self.app.add_handler(CommandHandler("verify", auth_handler.verify_command))
        self.app.add_handler(CommandHandler("help", auth_handler.help_command))
        self.app.add_handler(CommandHandler("status", auth_handler.status_command))
        
        # Admin commands
        self.app.add_handler(CommandHandler("set_token_requirement", admin_handler.set_token_requirement))
        self.app.add_handler(CommandHandler("set_nft_requirement", admin_handler.set_nft_requirement))
        self.app.add_handler(CommandHandler("list_requirements", admin_handler.list_requirements))
        self.app.add_handler(CommandHandler("ban_user", admin_handler.ban_user))
        self.app.add_handler(CommandHandler("unban_user", admin_handler.unban_user))
        self.app.add_handler(CommandHandler("stats", admin_handler.stats))
        
        # Message handlers
        self.app.add_handler(MessageHandler(
            filters.TEXT & filters.Regex(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$'), 
            verification_handler.handle_wallet_address
        ))
        
        self.app.add_handler(MessageHandler(
            filters.TEXT & filters.Regex(r'^[1-9A-HJ-NP-Za-km-z]{87,88}$'),
            verification_handler.handle_signature
        ))
        
        # Callback query handlers for inline keyboards
        self.app.add_handler(CallbackQueryHandler(verification_handler.handle_callback_query))
        
        # New member handler
        self.app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, webhook_handler.handle_new_member))
        
        # Error handler
        self.app.add_error_handler(self._error_handler)
    
    async def _error_handler(self, update, context):
        """Global error handler for the bot."""
        logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)
        
        # Notify user of error if possible
        if update and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "❌ An error occurred while processing your request. Please try again later."
                )
            except Exception as e:
                logger.error(f"Failed to send error message to user: {e}")
    
    async def start(self):
        """Start the bot."""
        try:
            await self.initialize()
            
            if settings.webhook_url:
                # Production mode with webhooks
                logger.info("Starting bot in webhook mode")
                await self.app.run_webhook(
                    listen="0.0.0.0",
                    port=8080,
                    webhook_url=settings.webhook_url,
                    secret_token=settings.webhook_secret
                )
            else:
                # Development mode with polling
                logger.info("Starting bot in polling mode")
                await self.app.run_polling(drop_pending_updates=True)
                
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        except Exception as e:
            logger.error(f"Bot crashed: {e}")
            raise
        finally:
            await self.cleanup()
    
    async def cleanup(self):
        """Clean up resources on shutdown."""
        try:
            if self.db_manager:
                await self.db_manager.close()
                logger.info("Database connection closed")
            
            if self.rate_limiter:
                await self.rate_limiter.close()
                logger.info("Rate limiter connection closed")
                
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


async def main():
    """Main application entry point."""
    try:
        bot = SuperteamBot()
        await bot.start()
    except Exception as e:
        logger.critical(f"Failed to start bot: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Handle Windows event loop policy
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # Run the bot
    asyncio.run(main())