from typing import List, Dict, Generator
import logging
from embedding_matcher import EmbeddingMatcher
import requests
import config
from database import ArticleDatabase
import google.generativeai as genai

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ArticleMatcher:
    def __init__(self, questions_text="", topics_text=""):
        self.matcher = EmbeddingMatcher()
        self.db = ArticleDatabase()
        self.questions_text = questions_text
        self.topics_text = topics_text
        
        # Initialize LLM based on environment
        if config.LLM_TYPE == "ollama":
            self.llm_url = f"{config.OLLAMA_BASE_URL}/api/generate"
            self.llm_model = config.OLLAMA_MODEL
        elif config.LLM_TYPE == "gemini":
            genai.configure(api_key=config.GEMINI_API_KEY)
            self.llm_model = genai.GenerativeModel(config.GEMINI_MODEL)
        
        logger.info(f"Initialized ArticleMatcher with {config.LLM_TYPE} LLM and database persistence")

    def _get_questions(self) -> List[str]:
        """Get questions and topics from either files or provided text"""
        try:
            questions = []
            
            if config.IS_STREAMLIT and (self.questions_text or self.topics_text):
                # Use provided text in Streamlit environment
                if self.questions_text:
                    questions.extend([line.strip("- ").strip() for line in self.questions_text.split("\n") if line.strip()])
                if self.topics_text:
                    questions.extend([line.strip("- ").strip() for line in self.topics_text.split("\n") if line.strip()])
            else:
                # Fall back to reading from files
                try:
                    # Read questions from question_list.md
                    with open("question_list.md", "r") as f:
                        content = f.read()
                        questions.extend([line.strip("- ").strip() for line in content.split("\n") if line.strip()])
                    
                    # Read topics from topic_list.md
                    with open("topic_list.md", "r") as f:
                        content = f.read()
                        topics = [line.strip("- ").strip() for line in content.split("\n") if line.strip()]
                        questions.extend(topics)
                except FileNotFoundError:
                    logger.warning("Question or topic files not found. Please provide questions and topics in the app.")
                    return []
            
            logger.info(f"Loaded {len(questions)} total items (questions + topics) for matching")
            return questions
        except Exception as e:
            logger.error(f"Error processing questions/topics: {str(e)}")
            return []

    def _verify_with_llm(self, article: Dict, question: str) -> Dict:
        """Verify article relevance with the configured LLM"""
        prompt = f"""Analyze if this article is relevant to the question/topic. 
        Respond with only 'yes' or 'no'.

        Article Title: {article['title']}
        Article Content: {article['content'][:1000]}  # Limit content length
        
        Question/Topic: {question}
        
        Is this article relevant to the question/topic?"""

        try:
            if config.LLM_TYPE == "ollama":
                response = requests.post(
                    self.llm_url,
                    json={
                        "model": self.llm_model,
                        "prompt": prompt,
                        "stream": False
                    }
                )
                response.raise_for_status()
                result = response.json()
                answer = result.get("response", "").strip().lower()
            else:  # Gemini
                response = self.llm_model.generate_content(prompt)
                answer = response.text.strip().lower()
            
            # Log the LLM's response
            logger.info(f"LLM verification for article '{article['title']}' and question '{question}': {answer}")
            
            return {
                "is_relevant": answer == "yes",
                "llm_response": answer
            }
        except Exception as e:
            logger.error(f"Error verifying with {config.LLM_TYPE}: {str(e)}")
            return {
                "is_relevant": False,
                "llm_response": f"Error: {str(e)}"
            }

    def process_article(self, article: Dict) -> Dict:
        """Process an article to find matching questions and topics using two-stage filtering"""
        questions = self._get_questions()
        
        try:
            logger.info(f"Processing article: {article['title']}")
            
            # First stage: Find similar questions/topics using embeddings
            similar_matches = self.matcher.find_similar(article["content"], questions)
            
            # Second stage: Verify matches with LLM
            verified_matches = []
            for match in similar_matches:
                verification = self._verify_with_llm(article, match["text"])
                if verification["is_relevant"]:
                    # Determine if this is a topic or question match
                    is_topic = match["text"] in [line.strip("- ").strip() for line in open("topic_list.md").read().split("\n") if line.strip()]
                    match_type = "topic" if is_topic else "question"
                    
                    verified_matches.append({
                        "question": match["text"],
                        "relevance": f"Verified {match_type} match (similarity: {match['score']:.2f})",
                        "llm_response": verification["llm_response"],
                        "type": match_type
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
