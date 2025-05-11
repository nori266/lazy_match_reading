import logging
from datetime import datetime
from typing import Optional, Dict, Any

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import TelegramError

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_NOTIFICATION_THRESHOLD

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        self.application: Optional[Application] = None

    async def start(self):
        """Initialize and start the Telegram bot."""
        if not TELEGRAM_BOT_TOKEN:
            logger.error("TELEGRAM_BOT_TOKEN not set in environment variables")
            return

        try:
            self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
            
            # Add command handlers
            self.application.add_handler(CommandHandler("start", self.start_command))
            self.application.add_handler(CommandHandler("help", self.help_command))
            
            # Start the bot
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()
            
            logger.info("Telegram bot started successfully")
        except Exception as e:
            logger.error(f"Failed to start Telegram bot: {e}")
            if self.application:
                await self.application.stop()
                await self.application.shutdown()

    async def stop(self):
        """Stop the Telegram bot."""
        if self.application:
            try:
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
            except Exception as e:
                logger.error(f"Error while stopping the bot: {e}")

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /start command."""
        await update.message.reply_text(
            "Welcome to Lazy Match Reading Bot! I'll notify you about relevant articles "
            "matching your interests. Use /help to see available commands."
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /help command."""
        help_text = """
Available commands:
/start - Start the bot
/help - Show this help message

The bot will automatically notify you about relevant articles matching your interests.
        """
        await update.message.reply_text(help_text)

    async def send_article_notification(self, article: Dict[str, Any], similarity_score: float):
        """Send a notification about a matching article."""
        if not self.application or similarity_score < TELEGRAM_NOTIFICATION_THRESHOLD:
            return

        try:
            # Format the message
            message = (
                f"📰 *New Matching Article*\n\n"
                f"*Title:* {article.get('title', 'N/A')}\n"
                f"*Source:* {article.get('source', 'N/A')}\n"
                f"*Date:* {article.get('published_at', 'N/A')}\n"
                f"*Similarity Score:* {similarity_score:.2f}\n\n"
                f"*Summary:* {article.get('summary', 'N/A')}\n\n"
                f"*Link:* {article.get('url', 'N/A')}"
            )

            # Send to specific chat if configured
            if TELEGRAM_CHAT_ID:
                await self.application.bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=message,
                    parse_mode='Markdown'
                )
            else:
                # If no specific chat ID, send to all subscribed users
                # This would require maintaining a list of subscribed users
                pass

            logger.info(f"Sent article notification: {article.get('title')}")
        except TelegramError as e:
            logger.error(f"Failed to send Telegram notification: {e}")

# Create a singleton instance
telegram_bot = TelegramBot() 