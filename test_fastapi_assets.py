from fastapi.testclient import TestClient
import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.abspath('backend'))

from app.main import app

client = TestClient(app)

print("--- 1. Testing GET /api/assets/images ---")
res = client.get("/api/assets/images")
print(f"Status: {res.status_code}")
if res.status_code == 200:
    data = res.json()
    print(f"Found {len(data)} images:")
    for img in data:
        print(f"  * {img.get('filename')} | category: {img.get('category')} | property: {img.get('property_name')} | url: {img.get('url')}")
else:
    print(f"Error: {res.text}")

print("\n--- 2. Testing Static Serving of an Image ---")
res_img = client.get("/api/assets/images/Bathroom.jpg")
print(f"Status: {res_img.status_code}")
print(f"Content-Type: {res_img.headers.get('content-type')}")
print(f"Size: {len(res_img.content)} bytes")

print("\n--- 3. Testing POST /api/chat with empty property search query ---")
payload = {
    "message": "Show me luxury penthouses in Paris under 1000 EUR",
    "provider": "ollama",
    "history": []
}
res_chat = client.post("/api/chat", json=payload)
print(f"Status: {res_chat.status_code}")
if res_chat.status_code == 200:
    chat_data = res_chat.json()
    print(f"Properties returned: {len(chat_data.get('properties', []))}")
    print(f"Images returned in payload: {len(chat_data.get('images', []))}")

