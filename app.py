import streamlit as st
import requests
import json
from datetime import datetime
import time
import sseclient
from database import ArticleDatabase
import config

# Configure the page
st.set_page_config(
    page_title="News Matcher",
    page_icon="📰",
    layout="wide"
)

# Custom CSS for better styling
st.markdown("""
    <style>
    .stApp {
        max-width: 1200px;
        margin: 0 auto;
    }
    .article-card {
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 10px;
        background-color: #f0f2f6;
    }
    .match-card {
        padding: 0.5rem;
        margin: 0.5rem 0;
        border-radius: 5px;
        background-color: #e6f3ff;
    }
    .article-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0.5rem;
    }
    .article-date {
        color: #666;
        font-size: 0.9em;
    }
    .new-article {
        border: 2px solid #4CAF50;
    }
    .match-card.topic {
        background-color: #e6ffe6;
    }
    .match-card.question {
        background-color: #e6f3ff;
    }
    </style>
    """, unsafe_allow_html=True)

# Title and description
st.title("📰 News Matcher")
st.markdown("""
This app matches news articles with your specific questions using AI.
Articles are fetched from Hacker News and TechCrunch.
""")

# Initialize database
db = ArticleDatabase()

# API endpoint configuration
if config.IS_STREAMLIT:
    # In Streamlit Share, we'll process articles directly
    API_URL = None
else:
    # Local development - connect to FastAPI server
    API_URL = "http://localhost:8000/fetch-news"

def format_date(date_str):
    """Format the date string to a more readable format"""
    try:
        if isinstance(date_str, str):
            # Try different date formats
            for fmt in ['%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%d']:
                try:
                    date = datetime.strptime(date_str, fmt)
                    return date.strftime('%B %d, %Y')
                except ValueError:
                    continue
        return date_str
    except Exception:
        return date_str

def display_article(article, is_new=False):
    """Display a single article with its matches"""
    # Format the date if available
    date_str = format_date(article.get('date', ''))
    
    # Add new-article class if it's a new article
    card_class = "article-card new-article" if is_new else "article-card"
    
    st.markdown(f"""
    <div class="{card_class}">
        <div class="article-header">
            <h3><a href="{article['url']}" target="_blank">{article['title']}</a></h3>
            <span class="article-date">{date_str}</span>
        </div>
        <p><em>Source: {article['source']}</em></p>
    """, unsafe_allow_html=True)
    
    for match in article['matches']:
        # Add different styling based on match type
        match_class = "match-card topic" if match['type'] == 'topic' else "match-card question"
        
        st.markdown(f"""
        <div class="{match_class}">
            <p><strong>Type:</strong> {match['type'].capitalize()}</p>
            <p><strong>Match:</strong> {match['question']}</p>
            <p><strong>Relevance:</strong> {match['relevance']}</p>
            <p><strong>LLM Response:</strong> {match['llm_response']}</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)

def process_articles_directly(questions_text="", topics_text=""):
    """Process articles directly in Streamlit environment"""
    from news_fetcher import NewsFetcher
    from llm_processor import ArticleMatcher
    
    news_fetcher = NewsFetcher()
    article_matcher = ArticleMatcher(questions_text=questions_text, topics_text=topics_text)
    
    articles = news_fetcher.fetch_all_articles()
    processed_articles = []
    
    for article in article_matcher.process_articles(articles):
        processed_articles.append(article)
        # Save to database
        db.save_article(article)
    
    return processed_articles

def main():
    st.title("News Matcher")
    
    # Initialize session state for articles if not exists
    if 'articles' not in st.session_state:
        st.session_state.articles = []
        # Load recent articles from database
        st.session_state.articles = db.get_recent_articles(limit=30)
    
    # Add text areas for questions and topics in Streamlit
    questions_text = ""
    topics_text = ""
    
    if config.IS_STREAMLIT:
        with st.sidebar:
            st.subheader("Questions & Topics")
            st.write("Enter your questions (one per line):")
            questions_text = st.text_area("Questions", height=200, 
                                       placeholder="Enter each question on a new line\nExample:\n- What are the latest developments in AI?\n- Any news about climate change?")
            
            st.write("Enter your topics of interest (one per line):")
            topics_text = st.text_area("Topics", height=200,
                                    placeholder="Enter each topic on a new line\nExample:\n- Artificial Intelligence\n- Climate Change\n- Space Exploration")
    
    # Add a refresh button
    if st.button("🔄 Refresh News"):
        st.session_state.last_refresh = datetime.now()
        st.session_state.articles = db.get_recent_articles(limit=30)  # Reload recent articles
        st.rerun()
    
    # Show last refresh time if available
    if 'last_refresh' in st.session_state:
        st.write(f"Last refreshed: {st.session_state.last_refresh.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Create a placeholder for the articles
    articles_placeholder = st.empty()
    
    # Display existing articles from database
    with articles_placeholder.container():
        st.subheader(f"Showing {len(st.session_state.articles)} most recent matching articles")
        for article in st.session_state.articles:
            display_article(article)
    
    # Fetch and display new news
    with st.spinner("Fetching and analyzing news articles..."):
        try:
            if API_URL:  # Local development - use FastAPI server
                # Create SSE client
                response = requests.get(API_URL, stream=True)
                client = sseclient.SSEClient(response)
                
                # Process each event as it arrives
                for event in client.events():
                    if event.data:
                        try:
                            data = json.loads(event.data)
                            if 'error' in data:
                                st.error(f"Error: {data['error']}")
                                break
                            
                            # Add new article to session state
                            st.session_state.articles.insert(0, data)  # Add to beginning
                            st.session_state.articles = st.session_state.articles[:30]  # Keep only 30 most recent
                            
                            # Update the display immediately for each new article
                            with articles_placeholder.container():
                                st.subheader(f"Showing {len(st.session_state.articles)} most recent matching articles")
                                # Display only the most recent article first
                                display_article(st.session_state.articles[0], is_new=True)
                                # Then display all previous articles
                                for article in st.session_state.articles[1:]:
                                    display_article(article)
                        except json.JSONDecodeError:
                            continue
            else:  # Streamlit Share - process articles directly
                if not questions_text.strip() and not topics_text.strip():
                    st.warning("Please enter some questions or topics to match against.")
                else:
                    with st.spinner("Processing articles with your questions and topics..."):
                        new_articles = process_articles_directly(questions_text, topics_text)
                        if new_articles:
                            st.session_state.articles = new_articles[:30]  # Keep only 30 most recent
                            st.rerun()  # Rerun to update the display with new articles
                        else:
                            st.info("No new matching articles found.")
                        
                        with articles_placeholder.container():
                            st.subheader(f"Showing {len(st.session_state.articles)} most recent matching articles")
                            for article in st.session_state.articles:
                                display_article(article)
        except Exception as e:
            st.error(f"Error processing articles: {str(e)}")
    
    # Display final results if no articles found
    if not st.session_state.articles:
        st.info("No matching articles found. Try refreshing or check if the API is running.")

if __name__ == "__main__":
    main() 