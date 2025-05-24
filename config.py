import os
import platform
from dotenv import load_dotenv

load_dotenv()

# Environment detection
# IS_MAC = platform.system() == "Darwin"
IS_MAC = False
IS_STREAMLIT = os.getenv("STREAMLIT_SERVER_RUNNING", "false").lower() == "true"

# News API configuration
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
NEWS_API_BASE_URL = "https://newsapi.org/v2"

# Hacker News API configuration
HN_API_BASE_URL = "https://hacker-news.firebaseio.com/v0"

# LLM Configuration
if IS_MAC:
    # Ollama configuration for Mac
    LLM_TYPE = "ollama"
    OLLAMA_BASE_URL = "http://localhost:11434"
    OLLAMA_MODEL = "llama3.1:8b"
elif IS_STREAMLIT:
    # Gemini configuration for Streamlit
    LLM_TYPE = "gemini"
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    # GEMINI_MODEL = "gemini-2.5-flash-preview-04-17"
    GEMINI_MODEL = "gemini-2.0-flash-lite"
else:
    # Default to Ollama if environment is not recognized
    LLM_TYPE = "ollama"
    OLLAMA_BASE_URL = "http://localhost:11434"
    OLLAMA_MODEL = "llama3.1:8b"

# News sources
SOURCES = [
    # "techcrunch",
    # "the-atlantic",
    "hacker-news"
]

# Number of articles to fetch per source
MAX_ARTICLES_PER_SOURCE = 30

# Telegram Bot configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # Optional: for direct messaging to specific chat
TELEGRAM_USER_ID = os.getenv("TELEGRAM_USER_ID")  # Your personal Telegram user ID
TELEGRAM_NOTIFICATION_THRESHOLD = 0.7  # Minimum similarity score to send notification

# Embedding Matcher configuration
EMBEDDING_SIMILARITY_THRESHOLD = 0.7  # Minimum similarity score for initial article filtering

TELEGRAM_BOT_TOKEN=os.getenv("TELEGRAM_BOT_TOKEN")
