import logging
import asyncio
import time
from datetime import datetime, timedelta
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
            self.application.add_handler(CommandHandler("timeframe", self.timeframe_command))
            
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
/recent - Get new articles matching your interests that haven't been sent yet
/timeframe [days] - Get articles from the last N days (default: 7) regardless of sent status
        """
        await update.message.reply_text(help_text)

    async def recent_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /recent command by sending unsent articles to the user."""
        await update.message.reply_text("Fetching new articles... Please wait.")
        try:
            # Get unsent articles from the database (limit to 5 to avoid message size limits)
            articles = self.db.get_unsent_telegram_articles(limit=5)
            
            if not articles:
                await update.message.reply_text("No new articles available. All articles have been sent!")
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
                    f"Showing {len(articles)} new articles. Use /help to see available commands."
                )
                
                # Mark all sent articles as sent
                for article in articles:
                    self.db.mark_article_sent_to_telegram(article['id'])              
        except Exception as e:
            logger.error(f"Error in recent_command: {e}")
            await update.message.reply_text(f"Error fetching articles: {str(e)}")

    async def timeframe_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /timeframe command to get articles from a specific timeframe."""
        # Default to 7 days if no argument is provided
        days = 7
        if context.args and len(context.args) > 0:
            try:
                days = int(context.args[0])
                if days <= 0:
                    await update.message.reply_text("Please provide a positive number of days.")
                    return
                if days > 30:
                    await update.message.reply_text("Maximum timeframe is 30 days.")
                    days = 30
            except ValueError:
                await update.message.reply_text("Please provide a valid number of days.")
                return
                
        await update.message.reply_text(f"Fetching articles from the last {days} days... Please wait.")
        
        try:
            # Calculate the date range
            end_date = datetime.now().isoformat()
            start_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            # Get articles within the timeframe
            articles = self.db.get_articles_by_timeframe(start_date, end_date, limit=10)
            
            if not articles:
                await update.message.reply_text(f"No articles found in the last {days} days.")
                return
                
            # Send each article with its matches
            sent_count = 0
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
                sent_status = "(Previously sent)" if article.get('sent_to_telegram', 0) == 1 else "(New)"
                message = (
                    f"📰 *Article* {sent_status}\n\n"
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
                sent_count += 1
                
                # Limit to 5 articles to avoid overloading
                if sent_count >= 5:
                    break
            
            # Inform user if all articles were sent
            if sent_count > 0:
                await update.message.reply_text(
                    f"Showing {sent_count} articles from the last {days} days. Use /help to see available commands."
                )
            else:
                await update.message.reply_text("No matching articles found in the specified timeframe.")
                
        except Exception as e:
            logger.error(f"Error in timeframe_command: {e}")
            await update.message.reply_text(f"Error fetching articles: {str(e)}")

    async def send_article_notification(self, article: Dict[str, Any], similarity_score: float):
        """Send a notification about a matching article."""
        if not self.application or similarity_score < TELEGRAM_NOTIFICATION_THRESHOLD:
            return
            
        # Get the article ID - articles may come from different sources
        article_id = None
        url = article.get('url')
        if url:
            # Look up the article by URL to get its ID
            db_article = self.db.get_article_by_url(url)
            if db_article and 'id' in db_article:
                article_id = db_article['id']
                
        # Skip if the article has already been sent
        if article_id is None:
            logger.warning(f"Could not find article ID for URL: {url}")
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
            
            # Mark the article as sent
            if article_id is not None:
                self.db.mark_article_sent_to_telegram(article_id)
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
