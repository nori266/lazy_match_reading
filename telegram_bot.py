import logging
import asyncio
import time
from datetime import datetime
from typing import Optional, Dict, Any

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import TelegramError

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_NOTIFICATION_THRESHOLD
from database import ArticleDatabase

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        self.application: Optional[Application] = None
        self.db = ArticleDatabase()

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
            self.application.add_handler(CommandHandler("recent", self.recent_command))
            
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
/recent - Get recent articles matching your interests
        """
        await update.message.reply_text(help_text)

    async def recent_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /recent command by sending recent articles to the user."""
        await update.message.reply_text("Fetching recent articles... Please wait.")
        try:
            # Get recent articles from the database (limit to 5 to avoid message size limits)
            articles = self.db.get_recent_articles(limit=5)
            
            if not articles:
                await update.message.reply_text("No articles found in the database.")
                return
                
            # Send each article with its matches
            for article in articles:
                if not article.get('matches', []):
                    continue  # Skip articles with no matches

                # Calculate max similarity score
                try:
                    max_score = max(
                        float(match.get('relevance').split('similarity: ')[1].split(')')[0]) 
                        for match in article['matches']
                    )
                except (ValueError, KeyError, IndexError):
                    max_score = 0.0

                # Format the message
                message = (
                    f"📰 *Article*\n\n"
                    f"*Title:* {article.get('title', 'N/A')}\n"
                    f"*Source:* {article.get('source', 'N/A')}\n"
                    f"*Date:* {article.get('date', 'N/A')}\n"
                    f"*Similarity Score:* {max_score:.2f}\n\n"
                )
                
                # Add summary of matches
                message += "*Matches:*\n"
                for match in article.get('matches', []):
                    message += f"- {match.get('question', 'N/A')} ({match.get('relevance', 'N/A')})\n"
                
                message += f"\n*Link:* {article.get('url', 'N/A')}"

                await update.message.reply_text(
                    text=message,
                    parse_mode='Markdown'
                )
                
            # Inform user if all articles were sent
            if len(articles) > 0:
                await update.message.reply_text(
                    f"Showing {len(articles)} recent articles. Use /help to see available commands."
                )
                
        except Exception as e:
            logger.error(f"Error in recent_command: {e}")
            await update.message.reply_text(f"Error fetching articles: {str(e)}")

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
                f"*Date:* {article.get('date', 'N/A')}\n"
                f"*Similarity Score:* {similarity_score:.2f}\n\n"
            )
            
            # Add summary of matches
            message += "*Matches:*\n"
            for match in article.get('matches', []):
                message += f"- {match.get('question', 'N/A')} ({match.get('relevance', 'N/A')})\n"
            
            message += f"\n*Link:* {article.get('url', 'N/A')}"

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

async def main():
    """Main function to run the Telegram bot directly."""
    await telegram_bot.start()
    
    try:
        # Keep the bot running
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        await telegram_bot.stop()

if __name__ == "__main__":
    # Run the main function
    asyncio.run(main()) 
