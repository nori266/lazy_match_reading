import json
from typing import List, Dict, Generator
import logging
from embedding_matcher import EmbeddingMatcher
import requests
import config
from database import ArticleDatabase

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ArticleMatcher:
    def __init__(self):
        self.matcher = EmbeddingMatcher()
        self.ollama_url = f"{config.OLLAMA_BASE_URL}/api/generate"
        self.db = ArticleDatabase()
        logger.info("Initialized ArticleMatcher with two-stage filtering and database persistence")

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

    def _verify_with_ollama(self, article: Dict, question: str) -> Dict:
        """Verify article relevance with Ollama"""
        prompt = f"""Analyze if this article is relevant to the question/topic. 
        Respond with only 'yes' or 'no'.

        Article Title: {article['title']}
        Article Content: {article['content'][:1000]}  # Limit content length
        
        Question/Topic: {question}
        
        Is this article relevant to the question/topic?"""

        try:
            response = requests.post(
                self.ollama_url,
                json={
                    "model": config.OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False
                }
            )
            response.raise_for_status()
            result = response.json()
            answer = result.get("response", "").strip().lower()
            
            # Log the LLM's response
            logger.info(f"LLM verification for article '{article['title']}' and question '{question}': {answer}")
            
            return {
                "is_relevant": answer == "yes",
                "llm_response": answer
            }
        except Exception as e:
            logger.error(f"Error verifying with Ollama: {str(e)}")
            return {
                "is_relevant": False,
                "llm_response": f"Error: {str(e)}"
            }

    def process_article(self, article: Dict) -> Dict:
        """Process an article to find matching questions using two-stage filtering"""
        questions = self._get_questions()
        
        try:
            logger.info(f"Processing article: {article['title']}")
            
            # First stage: Find similar questions using embeddings
            similar_matches = self.matcher.find_similar(article["content"], questions)
            
            # Second stage: Verify matches with Ollama
            verified_matches = []
            for match in similar_matches:
                verification = self._verify_with_ollama(article, match["text"])
                if verification["is_relevant"]:
                    verified_matches.append({
                        "question": match["text"],
                        "relevance": f"Verified match (similarity: {match['score']:.2f})",
                        "llm_response": verification["llm_response"]
                    })
            
            processed_article = {
                "title": article["title"],
                "url": article["url"],
                "source": article["source"],
                "content": article.get("content", ""),
                "date": article.get("date", ""),
                "matches": verified_matches
            }
            
            # Save to database if there are verified matches
            if verified_matches:
                self.db.save_article(processed_article)
                logger.info(f"Saved article '{article['title']}' to database")
            
            return processed_article
            
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
            if processed_article["matches"]:  # Only yield articles with verified matches
                yield processed_article
