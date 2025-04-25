import streamlit as st
import requests
import json
from datetime import datetime
import time
import sseclient

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
    </style>
    """, unsafe_allow_html=True)

# Title and description
st.title("📰 News Matcher")
st.markdown("""
This app matches news articles with your specific questions using AI.
Articles are fetched from Hacker News, TechCrunch, and The Atlantic.
""")

# API endpoint
API_URL = "http://localhost:8000/fetch-news"

def display_article(article):
    """Display a single article with its matches"""
    st.markdown(f"""
    <div class="article-card">
        <h3><a href="{article['url']}" target="_blank">{article['title']}</a></h3>
        <p><em>Source: {article['source']}</em></p>
    """, unsafe_allow_html=True)
    
    for match in article['matches']:
        st.markdown(f"""
        <div class="match-card">
            <p><strong>Question:</strong> {match['question']}</p>
            <p><strong>Relevance:</strong> {match['relevance']}</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)

def main():
    # Initialize session state for articles if not exists
    if 'articles' not in st.session_state:
        st.session_state.articles = []
    
    # Add a refresh button
    if st.button("🔄 Refresh News"):
        st.session_state.last_refresh = datetime.now()
        st.session_state.articles = []  # Clear previous articles
        st.experimental_rerun()
    
    # Show last refresh time if available
    if 'last_refresh' in st.session_state:
        st.write(f"Last refreshed: {st.session_state.last_refresh.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Create a placeholder for the articles
    articles_placeholder = st.empty()
    
    # Fetch and display news
    with st.spinner("Fetching and analyzing news articles..."):
        try:
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
                        st.session_state.articles.append(data)
                        
                        # Update the display
                        with articles_placeholder.container():
                            st.subheader(f"Found {len(st.session_state.articles)} matching articles")
                            for article in st.session_state.articles:
                                display_article(article)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            st.error(f"Error connecting to the API: {str(e)}")
    
    # Display final results if no streaming updates
    if not st.session_state.articles:
        st.info("No matching articles found. Try refreshing or check if the API is running.")

if __name__ == "__main__":
    main() 