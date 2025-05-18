from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from news_fetcher import NewsFetcher
from llm_processor import ArticleMatcher
import uvicorn
import json

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

news_fetcher = NewsFetcher()
article_matcher = ArticleMatcher()

@app.get("/")
async def root():
    return {"message": "News Matcher API is running"}

async def process_and_stream_articles():
    """Process articles and stream results as they become available"""
    try:
        # Fetch articles from all sources
        articles = news_fetcher.fetch_all_articles()
        
        # Process articles and stream results
        for processed_article in article_matcher.process_articles(articles):
            yield f"data: {json.dumps(processed_article)}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"

@app.get("/fetch-news")
async def fetch_news():
    """Stream news articles as they are processed"""
    return StreamingResponse(
        process_and_stream_articles(),
        media_type="text/event-stream"
    )

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 