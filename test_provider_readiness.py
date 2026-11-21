import sys
import os

sys.path.insert(0, os.path.abspath('backend'))

from fastapi.testclient import TestClient
from app.main import app
from app.config import env
from app.llm import extract, understand, _call_gemini_generate
from app.schemas import SearchFilters

client = TestClient(app)

print("=====================================================================")
print("TEST 1: HEALTH & PROVIDERS ENDPOINTS")
print("=====================================================================")

res_health = client.get("/health")
print(f"GET /health: {res_health.status_code}")
print(f"Payload: {res_health.json()}")
assert res_health.status_code == 200

res_providers = client.get("/api/providers")
print(f"\nGET /api/providers: {res_providers.status_code}")
print(f"Payload: {res_providers.json()}")
assert res_providers.status_code == 200

print("\n=====================================================================")
print("TEST 2: CORS PREFLIGHT VALIDATION FOR RENDER & LOCALHOST")
print("=====================================================================")

# Test from a Render frontend origin
headers_render = {
    "Origin": "https://estate-ai-demo.onrender.com",
    "Access-Control-Request-Method": "POST",
    "Access-Control-Request-Headers": "Content-Type",
}
res_cors_render = client.options("/api/chat", headers=headers_render)
print(f"OPTIONS /api/chat from https://estate-ai-demo.onrender.com: {res_cors_render.status_code}")
print(f"Allow-Origin header: {res_cors_render.headers.get('access-control-allow-origin')}")
assert res_cors_render.status_code == 200
assert res_cors_render.headers.get("access-control-allow-origin") in ["*", "https://estate-ai-demo.onrender.com"]

# Test from localhost origin
headers_local = {
    "Origin": "http://localhost:5173",
    "Access-Control-Request-Method": "POST",
    "Access-Control-Request-Headers": "Content-Type",
}
res_cors_local = client.options("/api/chat", headers=headers_local)
print(f"\nOPTIONS /api/chat from http://localhost:5173: {res_cors_local.status_code}")
print(f"Allow-Origin header: {res_cors_local.headers.get('access-control-allow-origin')}")
assert res_cors_local.status_code == 200

print("\n=====================================================================")
print("TEST 3: PROVIDER ISOLATION & ERROR REPORTING")
print("=====================================================================")

# Test 3A: Gemini with dummy key -> should raise clear descriptive error with actionable instructions
os.environ["GEMINI_API_KEY"] = "invalid_dummy_key_for_testing"
try:
    understand(provider="gemini", history=[], current="Show 2bhk in Bangalore under 80 lakhs")
    print("Gemini: Unexpected success with dummy key")
except Exception as e:
    print(f"Gemini error message (clean & informative): {e}")
    assert "Gemini" in str(e) or "API key" in str(e)

# Test 3B: Gemini with missing key -> should inform about Render environment variable
os.environ["GEMINI_API_KEY"] = ""
os.environ["GOOGLE_API_KEY"] = ""
try:
    understand(provider="gemini", history=[], current="Show 2bhk in Bangalore under 80 lakhs")
except Exception as e:
    print(f"Gemini missing key error: {e}")
    assert "GEMINI_API_KEY" in str(e)

# Test 3C: OpenAI with missing key -> should inform about Render environment variable
os.environ["OPENAI_API_KEY"] = ""
try:
    understand(provider="openai", history=[], current="Show 2bhk in Bangalore under 80 lakhs")
except Exception as e:
    print(f"OpenAI missing key error: {e}")
    assert "OPENAI_API_KEY" in str(e)

# Test 3D: Ollama -> should target local endpoint
try:
    understand(provider="ollama", history=[], current="Show 2bhk in Bangalore under 80 lakhs")
    print("Ollama: Successfully extracted (local Ollama running)")
except Exception as e:
    print(f"Ollama expected status: {e}")
    assert "Ollama" in str(e) or "11434" in str(e)

print("\n=====================================================================")
print("ALL TESTS PASSED SUCCESSFULLY!")
print("=====================================================================")

