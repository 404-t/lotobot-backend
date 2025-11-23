import json
from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

class RAGSystem:
    def __init__(self, model_name="intfloat/multilingual-e5-small"):
        self.model = SentenceTransformer(model_name)
        self.data = []
        self.embeddings = None
    
    def load_json(self, filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        texts = []
        for item in data:
            values = " ".join(str(v) for v in item.values())
            texts.append(values)
            self.data.append(item)
        
        self.embeddings = self.model.encode(texts)
    
    def search(self, query, top_k=3):
        query_embedding = self.model.encode([query])
        similarities = cosine_similarity(query_embedding, self.embeddings)[0]
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            results.append({
                "data": self.data[idx],
                "score": float(similarities[idx])
            })
        return results

