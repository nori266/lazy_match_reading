# News Matcher

AI-powered news filtering system that matches articles to your specific questions and topics. Uses a two-stage matching process combining embeddings and LLM verification (via Ollama) to find relevant news from various sources. Features a real-time Streamlit interface and persistent storage.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- Fetches news from multiple sources (Hacker News, TechCrunch)
- Uses Ollama for local LLM processing
- Two-stage article matching:
  - Fast initial filtering using embeddings (sentence-transformers)
  - Precise matching using LLM verification
- Supports both questions and topics for matching
- Provides relevance explanations for matches
- Beautiful Streamlit web interface for viewing results
- Persistent storage of matched articles using SQLite
- Real-time article processing with SSE (Server-Sent Events)

## Prerequisites

- Python 3.8+
- Ollama installed and running locally
- News API key

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file in the project root with your News API key:
```
NEWS_API_KEY=your_api_key_here
```

3. Make sure Ollama is running locally with the model specified in `config.py` (default: llama3.1:8b)

4. Create your question and topic lists:
   - Create `question_list.md` with your questions (one per line, prefixed with '- ')
   - Create `topic_list.md` with your topics (one per line, prefixed with '- ')

## Running the Application

### Option 1: API Only
1. Start the FastAPI server:
```bash
python main.py
```

2. The API will be available at `http://localhost:8000`

### Option 2: API + Streamlit Interface
1. Start the FastAPI server in one terminal:
```bash
python main.py
```

2. In another terminal, start the Streamlit interface:
```bash
streamlit run app.py
```

3. The Streamlit interface will be available at `http://localhost:8501`

## API Endpoints

- `GET /`: Health check endpoint
- `GET /fetch-news`: Fetches and processes news articles, returning matches with your questions

## Configuration

You can modify the following in `config.py`:
- News sources
- Number of articles to fetch per source
- Ollama model and URL
- News API configuration

## Database

The application uses SQLite to store:
- Matched articles
- Match details and scores
- Processing history

## Notes

- The application uses newspaper3k for article content extraction
- Make sure you have sufficient RAM for running the LLM model
- Processing time may vary depending on the number of articles and the LLM model used
- The Streamlit interface requires the FastAPI server to be running
- Articles are matched using both embedding similarity and LLM verification
- Only articles that pass both matching stages are stored and displayed

## Coming Soon

- Telegram bot integration for instant notifications
- Multi-user support with individual question/topic lists
- Question/topic management via Telegram commands
