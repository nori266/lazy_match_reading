import os
from dotenv import load_dotenv

load_dotenv()

# News API configuration
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
NEWS_API_BASE_URL = "https://newsapi.org/v2"

# Hacker News API configuration
HN_API_BASE_URL = "https://hacker-news.firebaseio.com/v0"

# Ollama configuration
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3.1:8b"  # Using llama3.1:8b model which is available in your installation

# News sources
SOURCES = [
    "techcrunch",
    "the-atlantic",
    "hacker-news"
]

# Number of articles to fetch per source
MAX_ARTICLES_PER_SOURCE = 10 