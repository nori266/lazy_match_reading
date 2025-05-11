from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List, Dict
import config

class EmbeddingMatcher:
    def __init__(self):
        self.model = SentenceTransformer('sentence-t5-base')
        self.index = None
        self.questions = []
        
    def encode_texts(self, texts: List[str]) -> np.ndarray:
        return self.model.encode(texts, normalize_embeddings=True)
    
    def find_similar(self, query: str, texts: List[str], top_k: int = 5) -> List[Dict]:
        query_embedding = self.encode_texts([query])
        text_embeddings = self.encode_texts(texts)
        
        # Calculate cosine similarities
        similarities = query_embedding @ text_embeddings.T
        
        # Get top matches
        top_indices = np.argsort(similarities[0])[-top_k:][::-1]
        
        return [
            {
                "text": texts[idx],
                "score": float(similarities[0][idx])
            }
            for idx in top_indices
            if similarities[0][idx] > config.EMBEDDING_SIMILARITY_THRESHOLD
        ]