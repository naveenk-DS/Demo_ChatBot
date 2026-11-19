import json
import logging
from typing import Any
import urllib.error
import urllib.request
from openai import OpenAI
from google import genai
from google.genai import types
from .config import env
from .schemas import SearchFilters

logger = logging.getLogger(__name__)

PROMPT = '''
You are a real-estate search assistant. Extract only information stated or safely implied.
Return JSON keys: intent, location, city, bhk, min_price, max_price, property_type,
needs_clarification, clarification_question, assistant_message.
intent is property_search, general_question, or contact_request.
Convert lakh amounts to integer INR (80 lakh = 8000000). "below 80 lakhs" means max_price=8000000.
Use conversation history to retain filters unless changed. Ask clarification rather than guessing.
Never invent property facts or availability. Do not generate SQL. Return JSON only.
'''

DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "qwen2.5:7b"


def conversation(history: list[dict[str, str]], current: str) -> list[dict[str, str]]:
    return history[-8:] + [{"role": "user", "content": current}]


def _normalize_extracted(data: dict[str, Any]) -> dict[str, Any]:
    """Ensures intent matches SearchFilters literals and cleans empty strings for optional fields."""
    raw_intent = str(data.get("intent", "property_search")).lower()
    if raw_intent in ("search", "find", "property_search", "buy", "rent"):
        data["intent"] = "property_search"
    elif raw_intent in ("general", "question", "general_question", "info", "faq"):
        data["intent"] = "general_question"
    elif raw_intent in ("contact", "enquiry", "inquiry", "contact_request"):
        data["intent"] = "contact_request"
    else:
        data["intent"] = "property_search"

    # Convert empty strings for optional numeric fields to None
    for k in ("bhk", "min_price", "max_price"):
        if k in data and (data[k] == "" or data[k] is None):
            data[k] = None

    # Convert empty strings for optional string fields to None
    for k in ("location", "city", "property_type", "clarification_question"):
        if k in data and isinstance(data[k], str) and not data[k].strip():
            data[k] = None

    return data


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
        return _normalize_extracted(json.loads(result.choices[0].message.content or "{}"))

    if provider == "gemini":
        key = env("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not configured.")
        client = genai.Client(api_key=key, http_options=types.HttpOptions(api_version="v1beta"))
        transcript = "\n".join(f'{m["role"]}: {m["content"]}' for m in turns)
        result = client.models.generate_content(
            model=env("GEMINI_MODEL", "gemini-2.5-flash"),
            contents=PROMPT + "\nConversation:\n" + transcript,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0),
        )
        return _normalize_extracted(json.loads(result.text or "{}"))

    if provider == "ollama":
        base_url = env("OLLAMA_BASE_URL", DEFAULT_OLLAMA_URL).rstrip("/")
        model = env("OLLAMA_CHAT_MODEL", env("OLLAMA_LLM_MODEL", DEFAULT_OLLAMA_MODEL))
        url = f"{base_url}/api/chat"

        payload = {
            "model": model,
            "messages": [{"role": "system", "content": PROMPT}] + turns,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.0},
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = data.get("message", {}).get("content", "").strip()
                if not content:
                    raise RuntimeError("Ollama returned an empty response.")
                parsed = json.loads(content)
                return _normalize_extracted(parsed)
        except urllib.error.HTTPError as he:
            if he.code == 404:
                raise RuntimeError(
                    f"Ollama model '{model}' is not available at {base_url}. "
                    f"Please run 'ollama pull {model}'."
                ) from he
            raise RuntimeError(f"Ollama API request failed with HTTP {he.code}: {he.reason}") from he
        except urllib.error.URLError as ue:
            raise ConnectionError(
                f"Ollama server is not running at {base_url}. "
                "Please start Ollama locally with 'ollama serve'."
            ) from ue
        except json.JSONDecodeError as je:
            raise ValueError(f"Ollama returned invalid JSON response: {je}") from je

    raise ValueError(f"Unsupported provider: '{provider}'. Supported providers are: openai, gemini, ollama.")


def understand(provider: str, history: list[dict[str, str]], current: str) -> SearchFilters:
    data = extract(provider, history, current)
    filters = SearchFilters.model_validate(data)
    if filters.min_price is not None and filters.max_price is not None and filters.min_price > filters.max_price:
        raise ValueError("Minimum price cannot exceed maximum price.")
    return filters
