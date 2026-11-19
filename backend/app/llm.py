import json
from typing import Any
from openai import OpenAI
from google import genai
from google.genai import types
from .config import env
from .schemas import SearchFilters

PROMPT = '''
You are a real-estate search assistant. Extract only information stated or safely implied.
Return JSON keys: intent, location, city, bhk, min_price, max_price, property_type,
needs_clarification, clarification_question, assistant_message.
intent is property_search, general_question, or contact_request.
Convert lakh amounts to integer INR (80 lakh = 8000000). "below 80 lakhs" means max_price=8000000.
Use conversation history to retain filters unless changed. Ask clarification rather than guessing.
Never invent property facts or availability. Do not generate SQL. Return JSON only.
'''

def conversation(history: list[dict[str, str]], current: str) -> list[dict[str, str]]:
    return history[-8:] + [{"role": "user", "content": current}]

def extract(provider: str, history: list[dict[str, str]], current: str) -> dict[str, Any]:
    turns = conversation(history, current)
    if provider == "openai":
        key = env("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not configured.")
        client = OpenAI(api_key=key)
        result = client.chat.completions.create(
            model=env("OPENAI_MODEL", "gpt-4.1-mini"),
            temperature=0,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": PROMPT}, *turns],
        )
        return json.loads(result.choices[0].message.content or "{}")
    if provider == "gemini":
        key = env("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not configured.")
        client = genai.Client(api_key=key, http_options=types.HttpOptions(api_version="v1beta"))
        transcript = "\n".join(f'{m["role"]}: {m["content"]}' for m in turns)
        result = client.models.generate_content(
            model=env("GEMINI_MODEL", "Gemini 2.5 Flash Lite"),
            contents=PROMPT + "\nConversation:\n" + transcript,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0),
        )
        return json.loads(result.text or "{}")
    raise ValueError("Unsupported provider.")

def understand(provider: str, history: list[dict[str, str]], current: str) -> SearchFilters:
    filters = SearchFilters.model_validate(extract(provider, history, current))
    if filters.min_price is not None and filters.max_price is not None and filters.min_price > filters.max_price:
        raise ValueError("Minimum price cannot exceed maximum price.")
    return filters
