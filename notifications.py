import logging
import httpx
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import streamlit as st
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_USER_ID, TELEGRAM_NOTIFICATION_THRESHOLD
from database import ArticleDatabase

# Set up logging
logger = logging.getLogger(__name__)

class NotificationManager:
    def __init__(self):
        self.db = ArticleDatabase()
        self.last_check_time = datetime.utcnow() - timedelta(minutes=5)  # Initial check
        self.enabled = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_USER_ID)
        
        if not self.enabled:
            logger.warning("Telegram notifications are not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_USER_ID in .env")

    async def send_telegram_message(self, message: str) -> bool:
        """Send a message via Telegram bot"""
        if not self.enabled:
            logger.warning("Telegram notifications are not enabled")
            return False
        
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_USER_ID:
            logger.error("Missing Telegram bot token or user ID")
            return False
            
        # Ensure message is not empty
        if not message or not message.strip():
            logger.error("Cannot send empty message")
            return False
            
        # Truncate message if too long (Telegram has a 4096 character limit)
        if len(message) > 4000:
            message = message[:4000] + "... [truncated]"
            
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        
        # Log the user ID being used
        logger.info(f"Attempting to send message to Telegram user ID: {TELEGRAM_USER_ID} (type: {type(TELEGRAM_USER_ID)})")
        
        # Try with HTML first, fallback to plain text if it fails
        for parse_mode in ["html", None]:
            # Ensure user_id is properly formatted
            try:
                # Try to convert to integer if it's a string that looks like a number
                user_id = int(TELEGRAM_USER_ID) if TELEGRAM_USER_ID.strip('-').isdigit() else TELEGRAM_USER_ID
            except (ValueError, AttributeError):
                user_id = TELEGRAM_USER_ID
                
            payload = {
                "chat_id": user_id,
                "text": message,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True
            }
            
            logger.info(f"Sending with payload chat_id: {user_id} (type: {type(user_id)})")

            
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(url, json=payload, timeout=10.0)
                    response_data = response.json()
                    
                    if response.is_success:
                        return True
                        
                    # Log the error response from Telegram
                    logger.error(f"Telegram API error: {response.status_code} - {response_data}")
                    logger.error(f"Full request payload: {payload}")
                    
                    # If it's a chat not found error, provide guidance
                    if response_data.get('description') == 'Bad Request: chat not found':
                        logger.error("The user ID was not found. Make sure you've run get_chat_id.py to get the correct user ID.")
                        logger.error("Also ensure your bot has been started by the user (send /start to the bot).")
                        logger.error("Your bot can only send messages to users who have initiated a conversation with it.")
                    
                    # If it's a 400 error with HTML, try again without HTML
                    if response.status_code == 400 and parse_mode == "HTML":
                        continue
                        
                    return False
                    
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error sending Telegram message: {e}")
                if parse_mode == "HTML":
                    continue  # Try again without HTML
                return False
                
            except Exception as e:
                logger.error(f"Unexpected error sending Telegram message: {e}")
                return False
                
        return False

    def get_new_articles(self) -> list:
        """Get articles added since last check"""
        # Get all recent articles
        all_articles = self.db.get_recent_articles(limit=100)  # Adjust limit as needed
        
        # Filter articles that are new since last check
        new_articles = []
        for article in all_articles:
            # Check if article is new since last check
            article_time = datetime.fromisoformat(article.get('created_at', ''))
            if article_time > self.last_check_time:
                # Check if any match meets the threshold
                for match in article.get('matches', []):
                    # Extract similarity score from the relevance string
                    try:
                        score_str = match.get('relevance', '').split('similarity: ')[1].split(')')[0]
                        score = float(score_str)
                        if score >= TELEGRAM_NOTIFICATION_THRESHOLD:
                            new_articles.append({
                                'id': article.get('url'),  # Using URL as ID since we don't have direct ID access
                                'title': article.get('title', 'No title'),
                                'url': article.get('url', ''),
                                'source': article.get('source', 'Unknown'),
                                'date': article.get('date', ''),
                                'question': match.get('question', ''),
                                'similarity_score': score,
                                'llm_response': match.get('llm_response', '')
                            })
                    except (IndexError, ValueError):
                        continue
        
        return new_articles

    async def check_and_notify(self):
        """Check for new articles and send notifications if found"""
        if not self.enabled:
            return
            
        try:
            new_articles = self.get_new_articles()
            
            for article in new_articles:
                message = (
                    f"📰 <b>New Article Match!</b>\n\n"
                    f"<b>Title:</b> {article['title']}\n"
                    f"<b>Source:</b> {article['source']}\n"
                    f"<b>Match Score:</b> {article['similarity_score']:.2f}\n"
                    f"<b>Question:</b> {article['question']}\n\n"
                    f"{article['llm_response']}\n\n"
                    f"🔗 <a href='{article['url']}'>Read more</a>"
                )
                await self.send_telegram_message(message)
                
            self.last_check_time = datetime.utcnow()
            logger.info(f"Checked for new articles. Found {len(new_articles)} new matches.")
            
        except Exception as e:
            logger.error(f"Error in check_and_notify: {e}")

# Create a singleton instance
notification_manager = NotificationManager()
