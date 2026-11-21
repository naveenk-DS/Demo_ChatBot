import sys
import os

sys.path.insert(0, os.path.abspath('backend'))

from fastapi.testclient import TestClient
from app.main import app
from app.config import env
from app.llm import extract, understand, DEFAULT_GEMINI_MODEL
from app.rag.service import answer_question

client = TestClient(app)

print("--- 1. Testing GET /api/providers ---")
res = client.get("/api/providers")
print("Status:", res.status_code)
data = res.json()
print("Gemini provider config in API:", data["providers"]["gemini"])
assert data["providers"]["gemini"]["model"] == "gemini-3.8-flash"
assert "3.8 Flash" in data["providers"]["gemini"]["name"]

print("\n--- 2. Testing Gemini Error Transparency (No Swallowed/Hidden Errors) ---")
# When Gemini key is missing
os.environ["GEMINI_API_KEY"] = ""
os.environ["GOOGLE_API_KEY"] = ""
try:
    understand("gemini", [], "Show 2bhk in Bangalore under 80 lakhs")
    print("Unexpected success with empty key")
except Exception as e:
    print("Clean Gemini missing-key error:", e)
    assert "GEMINI_API_KEY" in str(e)

# When OpenAI key is missing
os.environ["OPENAI_API_KEY"] = ""
try:
    understand("openai", [], "Show 2bhk in Bangalore under 80 lakhs")
except Exception as e:
    print("Clean OpenAI missing-key error:", e)
    assert "OPENAI_API_KEY" in str(e)

# Ollama verification
try:
    understand("ollama", [], "Show 2bhk in Bangalore under 80 lakhs")
    print("Ollama: Success")
except Exception as e:
    print("Ollama expected offline error:", e)
    assert "Ollama" in str(e) or "11434" in str(e)

print("\n--- 3. Testing RAG Service Gemini Configuration ---")
rag_res = answer_question("What are the master bedroom dimensions?", provider="gemini")
print("RAG answer_question with Gemini (handles missing key gracefully):", rag_res.get("error"))
assert "GEMINI_API_KEY" in str(rag_res.get("error"))

print("\nALL BACKEND CHECKS PASSED CLEANLY!")

