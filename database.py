import sqlite3
from datetime import datetime
from typing import List, Dict
import json

class ArticleDatabase:
    def __init__(self, db_path: str = "articles.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the database with required tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create articles table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    url TEXT UNIQUE NOT NULL,
                    source TEXT NOT NULL,
                    content TEXT,
                    date TEXT,
                    created_at TEXT NOT NULL,
                    verified_at TEXT NOT NULL
                )
            ''')
            
            # Create matches table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS matches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article_id INTEGER NOT NULL,
                    question TEXT NOT NULL,
                    similarity_score REAL NOT NULL,
                    llm_response TEXT NOT NULL,
                    FOREIGN KEY (article_id) REFERENCES articles (id)
                )
            ''')
            
            conn.commit()

    def save_article(self, article: Dict) -> int:
        """Save an article and its matches to the database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Insert article
            cursor.execute('''
                INSERT OR IGNORE INTO articles 
                (title, url, source, content, date, created_at, verified_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                article['title'],
                article['url'],
                article['source'],
                article.get('content', ''),
                article.get('date', ''),
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
            
            # Get the article ID
            article_id = cursor.lastrowid
            if article_id is None:  # Article already exists
                cursor.execute('SELECT id FROM articles WHERE url = ?', (article['url'],))
                article_id = cursor.fetchone()[0]
            
            # Insert matches
            for match in article['matches']:
                cursor.execute('''
                    INSERT INTO matches 
                    (article_id, question, similarity_score, llm_response)
                    VALUES (?, ?, ?, ?)
                ''', (
                    article_id,
                    match['question'],
                    float(match['relevance'].split('similarity: ')[1].split(')')[0]),
                    match['llm_response']
                ))
            
            conn.commit()
            return article_id

    def get_all_articles(self) -> List[Dict]:
        """Retrieve all articles with their matches"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get all articles
            cursor.execute('''
                SELECT id, title, url, source, content, date, created_at, verified_at
                FROM articles
                ORDER BY verified_at DESC
            ''')
            articles = []
            
            for row in cursor.fetchall():
                article_id, title, url, source, content, date, created_at, verified_at = row
                
                # Get matches for this article
                cursor.execute('''
                    SELECT question, similarity_score, llm_response
                    FROM matches
                    WHERE article_id = ?
                ''', (article_id,))
                
                matches = [
                    {
                        'question': question,
                        'relevance': f'Verified match (similarity: {score:.2f})',
                        'llm_response': llm_response
                    }
                    for question, score, llm_response in cursor.fetchall()
                ]
                
                articles.append({
                    'title': title,
                    'url': url,
                    'source': source,
                    'content': content,
                    'date': date,
                    'created_at': created_at,
                    'verified_at': verified_at,
                    'matches': matches
                })
            
            return articles

    def get_article_by_url(self, url: str) -> Dict:
        """Retrieve a specific article by its URL"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, title, url, source, content, date, created_at, verified_at
                FROM articles
                WHERE url = ?
            ''', (url,))
            
            row = cursor.fetchone()
            if not row:
                return None
                
            article_id, title, url, source, content, date, created_at, verified_at = row
            
            # Get matches
            cursor.execute('''
                SELECT question, similarity_score, llm_response
                FROM matches
                WHERE article_id = ?
            ''', (article_id,))
            
            matches = [
                {
                    'question': question,
                    'relevance': f'Verified match (similarity: {score:.2f})',
                    'llm_response': llm_response
                }
                for question, score, llm_response in cursor.fetchall()
            ]
            
            return {
                'title': title,
                'url': url,
                'source': source,
                'content': content,
                'date': date,
                'created_at': created_at,
                'verified_at': verified_at,
                'matches': matches
            }

    def get_recent_articles(self, limit: int = 30) -> List[Dict]:
        """Retrieve recent articles with their matches, limited by count"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get recent articles
            cursor.execute('''
                SELECT id, title, url, source, content, date, created_at, verified_at
                FROM articles
                ORDER BY verified_at DESC
                LIMIT ?
            ''', (limit,))
            articles = []
            
            for row in cursor.fetchall():
                article_id, title, url, source, content, date, created_at, verified_at = row
                
                # Get matches for this article
                cursor.execute('''
                    SELECT question, similarity_score, llm_response
                    FROM matches
                    WHERE article_id = ?
                ''', (article_id,))
                
                matches = [
                    {
                        'question': question,
                        'relevance': f'Verified match (similarity: {score:.2f})',
                        'llm_response': llm_response
                    }
                    for question, score, llm_response in cursor.fetchall()
                ]
                
                articles.append({
                    'title': title,
                    'url': url,
                    'source': source,
                    'content': content,
                    'date': date,
                    'created_at': created_at,
                    'verified_at': verified_at,
                    'matches': matches
                })
            
            return articles 