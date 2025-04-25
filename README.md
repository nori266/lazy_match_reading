# News Matcher

A Python application that matches news articles to your specific questions using Ollama and various news sources.

## Features

- Fetches news from multiple sources (Hacker News, TechCrunch, The Atlantic)
- Uses Ollama for local LLM processing
- Matches articles to your specific questions
- Provides relevance explanations for matches
- Beautiful Streamlit web interface for viewing results

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

3. Make sure Ollama is running locally with the model specified in `config.py` (default: llama2)

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

## Notes

- The application uses newspaper3k for article content extraction
- Make sure you have sufficient RAM for running the LLM model
- Processing time may vary depending on the number of articles and the LLM model used
- The Streamlit interface requires the FastAPI server to be running 