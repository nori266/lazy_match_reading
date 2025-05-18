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

    def _verify_with_llm(self, article: Dict, questions: List[str]) -> List[Dict]:
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
                response_text = result.get("response", "")
            else:  # Gemini
                response = self.llm_model.generate_content(prompt)
                response_text = response.text
            
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
            logger.error(f"Error verifying with {config.LLM_TYPE}: {str(e)}")
            # Return default 'no' for all questions in case of error
            return [{
                'question': q,
                'is_relevant': False,
                'llm_response': f"Error: {str(e)}"
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
                # Group matches by type for batch processing
                matches_by_type = {}
                for match in similar_matches:
                    is_topic = match["text"] in [line.strip("- ").strip() for line in open("topic_list.md").read().split("\n") if line.strip()]
                    match_type = "topic" if is_topic else "question"
                    matches_by_type.setdefault(match_type, []).append(match)
                
                # Process all matches in batches by type
                verified_matches = []
                for match_type, matches in matches_by_type.items():
                    questions = [m["text"] for m in matches]
                    verifications = self._verify_with_llm(article, questions)
                    
                    for match, verification in zip(matches, verifications):
                        if verification["is_relevant"]:
                            verified_matches.append({
                                "question": match["text"],
                                "relevance": f"Verified {match_type} match (similarity: {match['score']:.2f})",
                                "llm_response": verification["llm_response"],
                                "type": match_type
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
