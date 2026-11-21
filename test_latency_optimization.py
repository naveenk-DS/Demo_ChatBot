import sys
import os
import time

sys.path.insert(0, os.path.abspath('backend'))

from fastapi.testclient import TestClient
from app.main import app
from app.rag.retriever import hybrid_search
from app.rag.store import is_ollama_reachable

print("=====================================================================")
print("STAGE-BY-STAGE LATENCY MEASUREMENT")
print("=====================================================================")

# 1. Ollama Reachability Check (Cached)
t0 = time.perf_counter()
reachable = is_ollama_reachable()
t1 = time.perf_counter()
print(f"1. Ollama Reachability Check: {t1 - t0:.4f}s (Result: {reachable})")

# 2. Document Retrieval & Hybrid RRF (Run 1: warming cache)
t0 = time.perf_counter()
chunks1 = hybrid_search("What are the 2BHK specifications?", configuration="2BHK")
t1 = time.perf_counter()
print(f"2. Hybrid Search (Run 1 - Cold Index): {t1 - t0:.4f}s (Retrieved: {len(chunks1)} chunks)")

# 3. Document Retrieval & Hybrid RRF (Run 2: using in-memory cached BM25 index)
t0 = time.perf_counter()
chunks2 = hybrid_search("What are the 2BHK specifications?", configuration="2BHK")
t1 = time.perf_counter()
print(f"3. Hybrid Search (Run 2 - Warm Cache): {t1 - t0:.4f}s (Retrieved: {len(chunks2)} chunks)")

client = TestClient(app)

# 4. Fast-path query execution in /api/chat
t0 = time.perf_counter()
res = client.post("/api/chat", json={
    "message": "What are the 2BHK specifications?",
    "provider": "ollama",
    "history": []
})
t1 = time.perf_counter()
print(f"4. Total Chat Fast-path Routing + Retrieval: {t1 - t0:.4f}s (Status: {res.status_code})")

print("\nAll latency stages measured successfully!")

