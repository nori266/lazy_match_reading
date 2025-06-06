from typing import List, Dict, Generator
import logging
import time
from embedding_matcher import EmbeddingMatcher
import requests
import config
from database import ArticleDatabase
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ArticleMatcher:
    def __init__(self, input_text=""):
        self.matcher = EmbeddingMatcher()
        self.db = ArticleDatabase()
        self.input_text = input_text
        
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
            
            if config.IS_STREAMLIT and self.input_text:
                # Use provided text in Streamlit environment
                questions.extend([line.strip("- ").strip() for line in self.input_text.split("\n") if line.strip()])
            else:
                # Fall back to reading from files
                try:
                    # Read from both files into a single list
                    for filename in ["question_list.md", "topic_list.md"]:
                        try:
                            with open(filename, "r") as f:
                                content = f.read()
                                questions.extend([line.strip("- ").strip() for line in content.split("\n") if line.strip()])
                        except FileNotFoundError:
                            logger.warning(f"{filename} not found, skipping...")
                    
                    if not questions:
                        logger.warning("No questions or topics found in files. Please provide input in the app.")
                        return []
                except Exception as e:
                    logger.warning(f"Error reading files: {str(e)}. Please provide input in the app.")
                    return []
            
            logger.info(f"Loaded {len(questions)} total items for matching")
            return questions
        except Exception as e:
            logger.error(f"Error processing input: {str(e)}")
            return []

    def _verify_with_llm(self, article: Dict, questions: List[str], retry_count: int = 3) -> List[Dict]:
        """Verify article relevance against multiple questions/topics with a single LLM call"""
        if not questions:
            return []
            
        # Create a numbered list of questions for the prompt
        questions_list = '\n'.join([f"{i+1}. {q}" for i, q in enumerate(questions)])
        
        prompt = f"""Analyze if this article is relevant to each of the following questions/topics. 
For each question, respond with a single line containing the question number followed by 'yes' or 'no'.

Article Title: {article['title']}
Article Content: {article['content'][:2000]}  # Limit content length

Questions/Topics:
{questions_list}

For each question above, respond with the question number followed by 'yes' or 'no' on separate lines. 
Example:
1. yes
2. no
3. no"""

        last_exception = None
        for attempt in range(retry_count):
            try:
                if config.LLM_TYPE == "ollama":
                    try:
                        response = requests.post(
                            self.llm_url,
                            json={
                                "model": self.llm_model,
                                "prompt": prompt,
                                "stream": False
                            },
                            timeout=60  # Add timeout to prevent hanging
                        )
                        response.raise_for_status()
                        result = response.json()
                        response_text = result.get("response", "")
                    except requests.exceptions.RequestException as e:
                        if hasattr(e, 'response') and hasattr(e.response, 'status_code') and e.response.status_code == 429 and attempt < retry_count - 1:
                            wait_time = 60  # Wait for 60 seconds
                            logger.warning(f"Rate limited (429). Waiting for {wait_time} seconds before retry (attempt {attempt + 1}/{retry_count})")
                            time.sleep(wait_time)
                            last_exception = e
                            continue
                        raise
                else:  # Gemini
                    try:
                        response = self.llm_model.generate_content(prompt)
                        response_text = response.text
                    except google_exceptions.ResourceExhausted as e:
                        if "quota" in str(e).lower() and attempt < retry_count - 1:
                            wait_time = 60  # Wait for 60 seconds
                            logger.warning(f"Quota exceeded. Waiting for {wait_time} seconds before retry (attempt {attempt + 1}/{retry_count})")
                            time.sleep(wait_time)
                            last_exception = e
                            continue
                        raise
                    except Exception as e:
                        logger.error(f"Gemini API error: {str(e)}")
                        last_exception = e
                        if attempt < retry_count - 1:
                            time.sleep(5)  # Shorter delay for non-quota related errors
                            continue
                        raise

                # Parse the response into a dictionary of {question: answer}
                answers = {}
                for line in response_text.split('\n'):
                    line = line.strip()
                    if not line or not line[0].isdigit():
                        continue
                    try:
                        # Extract question number and answer (e.g., "1. yes" -> (0, "yes"))
                        parts = line.split('.', 1)
                        if len(parts) == 2:
                            q_num = int(parts[0].strip()) - 1  # Convert to 0-based index
                            answer = parts[1].strip().lower()
                            if 0 <= q_num < len(questions):
                                answers[questions[q_num]] = answer
                    except (ValueError, IndexError):
                        continue
                
                # Log the LLM's response
                logger.info(f"LLM verification for article '{article['title']}' completed with {len(answers)} answers")
                
                # Return list of results in the same order as input questions
                results = []
                for q in questions:
                    answer = answers.get(q, 'no')  # Default to 'no' if answer not found
                    results.append({
                        'question': q,
                        'is_relevant': answer == 'yes',
                        'llm_response': answer
                    })
                
                return results
                
            except Exception as e:
                last_exception = e
                if attempt == retry_count - 1:  # Last attempt
                    logger.error(f"Error verifying with {config.LLM_TYPE} after {retry_count} attempts: {str(e)}")
                    break
                time.sleep(5)  # Default delay between retries
                continue
        
        # If we get here, all retries failed
        error_msg = str(last_exception) if last_exception else "Unknown error"
        return [{
            'question': q,
            'is_relevant': False,
            'llm_response': f"Error: {error_msg}"
        } for q in questions]

    def process_article(self, article: Dict) -> Dict:
        """Process an article to find matching questions and topics using two-stage filtering"""
        questions = self._get_questions()
        
        try:
            logger.info(f"Processing article: {article['title']}")
            
            # First stage: Find similar questions/topics using embeddings
            similar_matches = self.matcher.find_similar(article["content"], questions)
            
            # Second stage: Verify matches with LLM (batch verification)
            if similar_matches:
                # Process all matches in a single batch
                questions = [m["text"] for m in similar_matches]
                verifications = self._verify_with_llm(article, questions)
                
                verified_matches = []
                for match, verification in zip(similar_matches, verifications):
                    if verification["is_relevant"]:
                        verified_matches.append({
                            "question": match["text"],
                            "relevance": f"Verified match (similarity: {match['score']:.2f})",
                            "llm_response": verification["llm_response"],
                            "type": "match"
                        })
            else:
                verified_matches = []
            
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
