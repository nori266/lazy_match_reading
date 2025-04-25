import json
from typing import List, Dict, Generator
import logging
from embedding_matcher import EmbeddingMatcher

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ArticleMatcher:
    def __init__(self):
        self.matcher = EmbeddingMatcher()
        logger.info("Initialized ArticleMatcher with BGE embeddings")

    def _get_questions(self) -> List[str]:
        """Read questions from the question list file"""
        try:
            with open("question_list.md", "r") as f:
                content = f.read()
                # Split by newlines and filter out empty lines
                questions = [line.strip("- ").strip() for line in content.split("\n") if line.strip()]
                logger.info(f"Loaded {len(questions)} questions from question_list.md")
                return questions
        except Exception as e:
            logger.error(f"Error reading questions: {str(e)}")
            return []

    def process_article(self, article: Dict) -> Dict:
        """Process an article to find matching questions"""
        questions = self._get_questions()
        
        try:
            logger.info(f"Processing article: {article['title']}")
            
            # Find similar questions using embeddings
            similar_matches = self.matcher.find_similar(article["content"], questions)
            
            # Convert to the expected format
            matches = [
                {
                    "question": match["text"],
                    "relevance": f"Similarity score: {match['score']:.2f}"
                }
                for match in similar_matches
            ]
            
            return {
                "title": article["title"],
                "url": article["url"],
                "source": article["source"],
                "matches": matches
            }
            
        except Exception as e:
            logger.error(f"Error processing article {article['title']}: {str(e)}")
            return {
                "title": article["title"],
                "url": article["url"],
                "source": article["source"],
                "matches": []
            }

    def process_articles(self, articles: List[Dict]) -> Generator[Dict, None, None]:
        """Process multiple articles and yield results one by one"""
        for article in articles:
            processed_article = self.process_article(article)
            if processed_article["matches"]:  # Only yield articles with matches
                yield processed_article
