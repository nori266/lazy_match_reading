import requests
from typing import List, Dict
import config
from newspaper import Article
import json
from datetime import datetime

class NewsFetcher:
    def __init__(self):
        self.news_api_key = config.NEWS_API_KEY
        self.hn_api_url = config.HN_API_BASE_URL

    def fetch_news_api_articles(self, source: str) -> List[Dict]:
        """Fetch articles from News API sources"""
        url = f"{config.NEWS_API_BASE_URL}/everything"
        params = {
            "sources": source,
            "apiKey": self.news_api_key,
            "pageSize": config.MAX_ARTICLES_PER_SOURCE
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            articles = response.json().get("articles", [])
            return [{
                "title": article["title"],
                "url": article["url"],
                "source": source,
                "date": article.get("publishedAt", ""),
                "content": self._get_article_content(article["url"])
            } for article in articles]
        except Exception as e:
            print(f"Error fetching from {source}: {str(e)}")
            return []

    def fetch_hacker_news(self) -> List[Dict]:
        """Fetch top stories from Hacker News"""
        try:
            # Get top stories IDs
            response = requests.get(f"{self.hn_api_url}/topstories.json")
            response.raise_for_status()
            story_ids = response.json()[:config.MAX_ARTICLES_PER_SOURCE]

            articles = []
            for story_id in story_ids:
                story_response = requests.get(f"{self.hn_api_url}/item/{story_id}.json")
                story_data = story_response.json()
                
                if story_data.get("url"):
                    # Convert Unix timestamp to ISO format
                    date = datetime.fromtimestamp(story_data.get("time", 0)).isoformat() if story_data.get("time") else ""
                    articles.append({
                        "title": story_data.get("title", ""),
                        "url": story_data.get("url"),
                        "source": "hacker-news",
                        "date": date,
                        "content": self._get_article_content(story_data.get("url"))
                    })
            return articles
        except Exception as e:
            print(f"Error fetching Hacker News: {str(e)}")
            return []

    def _get_article_content(self, url: str) -> str:
        """Extract article content using newspaper3k"""
        try:
            article = Article(url)
            article.download()
            article.parse()
            return article.text
        except Exception as e:
            print(f"Error extracting content from {url}: {str(e)}")
            return ""

    def fetch_all_articles(self) -> List[Dict]:
        """Fetch articles from all configured sources"""
        all_articles = []
        
        # Fetch from News API sources
        for source in config.SOURCES:
            if source != "hacker-news":
                articles = self.fetch_news_api_articles(source)
                all_articles.extend(articles)
        
        # Fetch from Hacker News
        hn_articles = self.fetch_hacker_news()
        all_articles.extend(hn_articles)
        
        return all_articles 