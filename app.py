import streamlit as st
from datetime import datetime
import time
from database import ArticleDatabase
from notifications import notification_manager
import asyncio
from streamlit.runtime.scriptrunner import add_script_run_ctx

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

def process_articles_directly(input_text=""):
    """Process articles directly in Streamlit environment"""
    from news_fetcher import NewsFetcher
    from llm_processor import ArticleMatcher
    
    news_fetcher = NewsFetcher()
    article_matcher = ArticleMatcher(input_text=input_text)
    
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
        st.session_state.articles = db.get_recent_articles(limit=30)
    
    # Refresh button
    if st.button("🔄 Refresh"):
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
            # Create input area for questions and topics
            input_text = st.text_area(
                "Enter your questions or topics (one per line)",
                height=200,
                help="Enter each question or topic on a new line. Topics are broader and will match more articles than specific questions."
            )
            
            # Process button
            if st.button("Process Articles"):
                # Check if any input is provided
                if not input_text.strip():
                    st.warning("Please enter some questions or topics to match against.")
                else:
                    with st.spinner("Processing articles with your questions and topics..."):
                        new_articles = process_articles_directly(input_text)
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

def check_notifications_periodically():
    """Check for new notifications periodically"""
    while True:
        try:
            # Get the current script run context
            ctx = st.runtime.scriptrunner.get_script_run_ctx()
            if ctx is None:
                # If running in a thread without context, create a new one
                from streamlit.runtime.scriptrunner import add_script_run_ctx
                import threading
                ctx = add_script_run_ctx(threading.current_thread())
            
            if st.session_state.get('notifications_enabled', False):
                # Run the async function in the event loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(notification_manager.check_and_notify())
                loop.close()
            
            # Sleep for 5 minutes between checks
            time.sleep(3600)
            
        except Exception as e:
            print(f"Error in notification thread: {e}")
            time.sleep(60)  # Wait a minute before retrying on error

if __name__ == "__main__":
    # Initialize session state for notifications
    if 'notifications_enabled' not in st.session_state:
        st.session_state.notifications_enabled = False
    
    # Add notification toggle to the sidebar
    with st.sidebar:
        st.subheader("🔔 Notifications")
        if not notification_manager.enabled:
            st.warning("Telegram notifications are not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_USER_ID in .env")
        else:
            new_status = st.toggle("Enable Notifications", 
                                value=st.session_state.notifications_enabled,
                                disabled=not notification_manager.enabled)
            
            if new_status != st.session_state.notifications_enabled:
                st.session_state.notifications_enabled = new_status
                st.rerun()
            
            if st.session_state.notifications_enabled:
                st.success("Notifications are enabled. You'll receive alerts for new matches.")
                # Start the notification check in a separate thread
                import threading
                from streamlit.runtime.scriptrunner import add_script_run_ctx
                
                if not hasattr(st.session_state, 'notification_thread') or not st.session_state.notification_thread.is_alive():
                    st.session_state.notification_thread = threading.Thread(
                        target=check_notifications_periodically,
                        daemon=True
                    )
                    # Add the Streamlit context to the thread
                    add_script_run_ctx(st.session_state.notification_thread)
                    st.session_state.notification_thread.start()
    
    main()
