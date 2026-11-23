import json
import logging
import re
from typing import Any, Optional
import urllib.error
import urllib.request
from openai import OpenAI
from google import genai
from google.genai import types
from .config import env
from .schemas import SearchFilters

logger = logging.getLogger(__name__)

PROMPT = '''
You are an intelligent real estate AI assistant.
Analyze the user's message and conversation history to accurately classify the intent and extract relevant search parameters.

JSON Output Schema:
{
  "intent": "property_search" | "document_qa" | "media_request" | "contact_request" | "general_question" | "search_refinement",
  "location": string or null,
  "city": string or null,
  "bhk": integer or null,
  "min_price": integer INR or null,
  "max_price": integer INR or null,
  "property_type": string or null,
  "needs_clarification": boolean,
  "clarification_question": string or null,
  "assistant_message": string or null
}

Intent Definitions:
1. "property_search": User is actively looking to search or buy properties by budget, city, location, or BHK (e.g. "I am looking for a property around 69 lakhs", "In Chennai", "Show 2BHK below 80 lakhs").
2. "document_qa": User is asking about property specifications, floor plans, room dimensions, entrance features, amenities, comparing 2BHK vs 3BHK, or checking bedroom counts (e.g. "What are the master bedroom dimensions?", "What are the entrance features?", "Does the 3BHK have five bedrooms?", "Give me details of all three bedrooms", "Compare 2BHK and 3BHK", "Which is better, 2BHK or 3BHK?", "What are the 2BHK specifications?", "Tell me about the 4BHK", "4BHK details").
3. "media_request": User is asking for images, photos, videos, or visual displays of rooms or the property (e.g. "Show me bathroom images", "Show bedroom images", "Show kitchen images", "Show master bedroom", "Show balcony", "Show me the property images", "Show me images").
4. "contact_request": User wants to schedule a site visit, request agent callback, or submit an inquiry.
5. "general_question": Greetings, small talk, or requests to clear/reset filters (e.g. "Hello", "Hi", "Thank you", "Forget the budget. I only want property specifications").
6. "search_refinement": User is refining or narrowing a previous property search result without changing the core subject (e.g. "Cheaper ones", "East facing only", "Near metro", "Show more", "Filter by 3BHK", "Under 70 lakhs", "With a garden", "Smaller ones"). Use only when there was a prior property search in the conversation history.

Context Handling & Clarification Rules:
- For "property_search": Retain previously specified search criteria (city, location, budget, bhk) from history unless modified or reset.
- If the user says "forget the budget", "ignore budget", "clear budget", or "reset", set min_price to null and max_price to null. Do NOT carry previous budget forward.
- For "document_qa": Document questions are INDEPENDENT of budget and location. Do NOT require city, budget, or property search criteria. Set needs_clarification to false.
- For "media_request": Set needs_clarification to false.
- For "property_search": Set needs_clarification to true ONLY when missing information genuinely prevents searching. If budget is provided but location/city is missing, ask specifically for the preferred city or locality (e.g. "I've noted your budget of around ₹69 Lakhs. Which city or locality are you looking for?").
- When the user answers the missing detail (e.g. "In Chennai"), combine it with the previously stated budget from history, set needs_clarification to false, and do NOT repeat the question.
- NEVER ask questions about images of land, blueprints, deeds, or unprompted property types.
- Convert lakh amounts to integer INR (e.g. 69 lakhs = 6900000, 80 lakhs = 8000000).
- If an optional filter is not specified or not mentioned, set its value to null (never strings like "not specified" or empty strings).
- Return valid JSON only.
'''

DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "qwen2.5:3b"
UNSPECIFIED_SENTINELS = {
    "",
    "null",
    "none",
    "not specified",
    "unspecified",
    "not mentioned",
    "n/a",
    "na",
    "any",
    "unknown",
    "all",
    "-",
    "nil",
    "undefined",
}


def conversation(history: list[dict[str, str]], current: str) -> list[dict[str, str]]:
    return history[-8:] + [{"role": "user", "content": current}]


def _normalize_extracted(data: dict[str, Any], current_query: str = "") -> dict[str, Any]:
    """Ensures intent matches SearchFilters literals, enforces intent safety, and cleans sentinel values."""
    raw_intent = str(data.get("intent", "property_search")).lower().strip()
    query_lower = current_query.lower().strip()

    # Rule 1: Media requests (images, photos, pictures, walkthroughs, or visual room requests)
    visual_action = any(
        query_lower.startswith(prefix) or f" {prefix} " in query_lower or query_lower.startswith(f"{prefix} ")
        for prefix in ["show me", "show", "display", "view", "see", "look at"]
    )
    has_room_term = any(
        term in query_lower
        for term in [
            "master bedroom", "bedroom", "bathroom", "kitchen", "balcony", "living",
            "dining", "hall", "entrance", "foyer", "terrace", "deck", "patio",
            "floor plan", "exterior", "elevation"
        ]
    )
    has_doc_qa_keyword = any(
        k in query_lower
        for k in [
            "dimension", "dimensions", "specification", "specifications", "size", "area",
            "sqft", "sq ft", "measure", "how many", "does the", "does it", "compare",
            "which is better", "detail", "details", "feature", "features", "what are"
        ]
    )
    has_search_criteria = any(
        k in query_lower
        for k in [
            "lakh", "crore", "budget", "price", "under", "below", "above",
            "in chennai", "in bangalore", "in mumbai", "in delhi", "in hyderabad",
            "for sale", "buy", "rent"
        ]
    )

    if any(k in query_lower for k in ["image", "images", "photo", "photos", "picture", "pictures", "video", "videos", "virtual tour", "gallery"]):
        data["intent"] = "media_request"
        data["needs_clarification"] = False
        data["clarification_question"] = None
    elif visual_action and has_room_term and not has_doc_qa_keyword and not has_search_criteria:
        data["intent"] = "media_request"
        data["needs_clarification"] = False
        data["clarification_question"] = None
    elif any(phrase in query_lower for phrase in ["that room", "this room", "the room", "show it", "show that", "show me that", "see it", "view it"]) and not has_doc_qa_keyword and not has_search_criteria:
        data["intent"] = "media_request"
        data["needs_clarification"] = False
        data["clarification_question"] = None

    # Rule 2: Explicit filter resets ("forget the budget", "ignore budget", etc.)
    elif any(k in query_lower for k in ["forget the budget", "forget budget", "ignore the budget", "ignore budget", "clear budget", "reset budget"]):
        data["intent"] = "general_question"
        data["min_price"] = None
        data["max_price"] = None
        data["needs_clarification"] = False
        data["clarification_question"] = None

    # Rule 3: Document QA (specifications, dimensions, comparisons, room counts, entrance, arbitrary documents)
    elif any(k in query_lower for k in [
        "dimension", "dimensions", "specification", "specifications", "document detail", "document details",
        "master bedroom", "entrance feature", "entrance features", "entrance",
        "which is better", "compare 2bhk", "compare 3bhk", "compare", "floor plan", "script",
        "all three bedrooms", "three bedrooms", "five bedrooms", "how many bedrooms",
        "does the 3bhk have", "does the 2bhk have", "does the 4bhk have", "balcony", "foyer", "amenities",
        "document", "pdf", "file", "agreement", "guideline", "guidelines", "rules", "policy", "policies",
        "terms", "condition", "conditions", "pricing", "cost", "fee", "fees", "clause", "clauses",
        "handbook", "brochure", "timeline", "possession", "maintenance", "security deposit"
    ]) or (
        re.search(r"\b[1-9]\s*bhk\b", query_lower)
        and any(w in query_lower for w in ["detail", "details", "info", "about", "spec", "plan", "document", "script", "what are", "tell me", "give me"])
        and not has_search_criteria
    ):
        data["intent"] = "document_qa"
        data["needs_clarification"] = False
        data["clarification_question"] = None

    # Rule 4a: Search refinement — user is narrowing a previous property search
    elif any(k in query_lower for k in [
        "cheaper", "more affordable", "lower price", "cheaper ones", "lower budget",
        "east facing", "west facing", "north facing", "south facing",
        "near metro", "near school", "near hospital", "near it park",
        "show more", "more options", "other options", "different options",
        "smaller", "bigger", "larger", "smaller area", "larger area",
        "with garden", "garden", "with pool", "with parking", "with gym", "with clubhouse",
        "ready to move", "under construction", "furnished", "unfurnished",
        "refine", "filter", "narrow", "only", "just show", "only show"
    ]) and raw_intent not in ("document_qa", "media_request", "contact_request", "general_question"):
        data["intent"] = "search_refinement"
        data["needs_clarification"] = False
        data["clarification_question"] = None

    # Rule 4b: Map raw intent strings
    elif raw_intent in ("media", "media_request", "image", "photo"):
        data["intent"] = "media_request"
    elif raw_intent in ("document", "doc", "document_qa", "spec", "specification", "specifications", "rag"):
        data["intent"] = "document_qa"
    elif raw_intent in ("search_refinement", "refine", "refinement", "filter"):
        data["intent"] = "search_refinement"
    elif raw_intent in ("contact", "enquiry", "inquiry", "contact_request", "visit"):
        data["intent"] = "contact_request"
    # Rule 5: Greeting / simple conversational messages — always general_question, check BEFORE raw_intent property_search mapping
    elif any(k in query_lower for k in [
        "hello", "hi", "hey", "good morning", "good afternoon", "good evening",
        "thanks", "thank you", "ok", "okay", "alright", "got it", "great", "nice",
        "who are you", "what can you do", "help me", "what is this", "what is estateai"
    ]):
        data["intent"] = "general_question"
    elif raw_intent in ("general", "question", "general_question", "info", "faq", "greeting"):
        data["intent"] = "general_question"
    elif raw_intent in ("search", "find", "property_search", "buy", "rent") or any(k in query_lower for k in ["bhk", "crore", "lakh", "budget", "apartment", "villa", "flat", "buy", "house", "for sale"]):
        data["intent"] = "property_search"
    else:
        # Safe fallback: general_question instead of blindly triggering a property search
        data["intent"] = "general_question"

    # Deterministic parameter extraction for offline / fallback robustness
    if data.get("intent") == "property_search":
        if not data.get("bhk"):
            bhk_m = re.search(r"\b([1-9])\s*bhk\b", query_lower)
            if bhk_m:
                data["bhk"] = int(bhk_m.group(1))
        if not data.get("max_price"):
            cr_m = re.search(r"(\d+(?:\.\d+)?)\s*crore", query_lower)
            lk_m = re.search(r"(\d+(?:\.\d+)?)\s*lakh", query_lower)
            if cr_m:
                data["max_price"] = int(float(cr_m.group(1)) * 10000000)
            elif lk_m:
                data["max_price"] = int(float(lk_m.group(1)) * 100000)
        if not data.get("location"):
            for loc in ["omr", "sholinganallur", "kelambakkam", "perungudi", "velachery", "guindy", "porur", "anna nagar"]:
                if loc in query_lower:
                    data["location"] = loc.upper() if loc == "omr" else loc.title()
                    break

    # Convert empty/sentinel strings for optional numeric fields to None
    for k in ("bhk", "min_price", "max_price"):
        if k in data:
            val = data[k]
            if val is None or (isinstance(val, str) and (not val.strip() or val.strip().lower() in UNSPECIFIED_SENTINELS)):
                data[k] = None
            elif isinstance(val, str):
                try:
                    data[k] = int(val.replace(",", "").strip())
                except ValueError:
                    data[k] = None

    # Convert empty/sentinel strings for optional string fields to None
    for k in ("location", "city", "property_type", "clarification_question"):
        if k in data:
            val = data[k]
            if val is None or (isinstance(val, str) and (not val.strip() or val.strip().lower() in UNSPECIFIED_SENTINELS)):
                data[k] = None

    # Sanitize clarification question: never hallucinate image-of-land questions
    if data.get("needs_clarification"):
        cq = str(data.get("clarification_question") or "").lower()
        if "image" in cq or "land" in cq or not cq.strip():
            if data.get("max_price"):
                lakhs = data["max_price"] // 100000
                data["clarification_question"] = f"I've noted your budget of around ₹{lakhs} Lakhs. Which city or locality are you looking for?"
            else:
                data["clarification_question"] = "Which city or locality and budget do you have in mind for your property search?"

    # Ensure document_qa, media_request, contact_request never trigger clarification
    if data.get("intent") in ("document_qa", "media_request", "contact_request"):
        data["needs_clarification"] = False
        data["clarification_question"] = None

    return data


DEFAULT_GEMINI_MODEL = env("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()

# Client instance caching to enable TCP/TLS keep-alive connection reuse
_cached_gemini_client: Optional[Any] = None
_cached_gemini_key: Optional[str] = None
_cached_openai_client: Optional[Any] = None
_cached_openai_key: Optional[str] = None


def get_gemini_client(api_key: str) -> Any:
    """Returns reused Gemini client instance with keep-alive connections.
    Note: google-genai types.HttpOptions.timeout expects MILLISECONDS (45000 ms = 45s)."""
    global _cached_gemini_client, _cached_gemini_key
    if _cached_gemini_client is not None and _cached_gemini_key == api_key:
        return _cached_gemini_client
    _cached_gemini_client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(api_version="v1beta", timeout=45000)
    )
    _cached_gemini_key = api_key
    return _cached_gemini_client


def get_openai_client(api_key: str) -> Any:
    """Returns reused OpenAI client instance with keep-alive connections."""
    global _cached_openai_client, _cached_openai_key
    if _cached_openai_client is not None and _cached_openai_key == api_key:
        return _cached_openai_client
    _cached_openai_client = OpenAI(api_key=api_key, timeout=30)
    _cached_openai_key = api_key
    return _cached_openai_client


def _call_gemini_generate(client: Any, contents: Any, config: Any, model_name: str) -> str:
    """Calls Gemini API with the configured model and surfaces precise error diagnostics."""
    try:
        result = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=config,
        )
        return result.text or ""
    except Exception as e:
        err_str = str(e)
        # Fallback to high-speed gemini-3.5-flash-lite if primary model experiences 503 high demand spikes or 404
        if ("503" in err_str or "high demand" in err_str.lower() or "404" in err_str or "not found" in err_str.lower()) and model_name != "gemini-3.5-flash-lite":
            logger.warning("Gemini model '%s' unavailable (%s); falling back to gemini-3.5-flash-lite.", model_name, err_str)
            try:
                res_fallback = client.models.generate_content(
                    model="gemini-3.5-flash-lite",
                    contents=contents,
                    config=config,
                )
                return res_fallback.text or ""
            except Exception as fb_err:
                logger.error("Gemini fallback also failed: %s", fb_err)

        if "API_KEY_INVALID" in err_str or "API key not valid" in err_str:
            raise RuntimeError(
                "Your Gemini API key is invalid or not activated. "
                "Please verify GEMINI_API_KEY in Render Environment Variables (from https://aistudio.google.com/apikey)."
            ) from e
        if "timed out" in err_str.lower() or "timeout" in err_str.lower():
            raise TimeoutError("Gemini API request timed out. Please try again.") from e
        if "404" in err_str or "not found" in err_str.lower():
            raise RuntimeError(
                f"Gemini model '{model_name}' was not found (HTTP 404). "
                f"Please ensure GEMINI_MODEL={DEFAULT_GEMINI_MODEL} is configured in Render Environment Variables."
            ) from e
        raise


def extract(provider: str, history: list[dict[str, str]], current: str) -> dict[str, Any]:
    turns = conversation(history, current)
    if provider == "openai":
        key = env("OPENAI_API_KEY")
        if not key:
            raise RuntimeError(
                "OPENAI_API_KEY is not configured in environment variables. "
                "Please configure OPENAI_API_KEY in Render Environment Variables."
            )
        client = get_openai_client(key)
        try:
            result = client.chat.completions.create(
                model=env("OPENAI_MODEL", "gpt-4.1-mini"),
                temperature=0,
                response_format={"type": "json_object"},
                messages=[{"role": "system", "content": PROMPT}, *turns],
            )
            return _normalize_extracted(json.loads(result.choices[0].message.content or "{}"), current)
        except Exception as e:
            err_str = str(e).lower()
            if "invalidated" in err_str or "401" in err_str or "incorrect api key" in err_str:
                raise RuntimeError(
                    "Your OpenAI API key is invalid, expired, or has insufficient quota. "
                    "Please verify OPENAI_API_KEY in Render Environment Variables (from https://platform.openai.com/api-keys)."
                ) from e
            raise

    if provider == "gemini":
        key = env("GEMINI_API_KEY") or env("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError(
                "GEMINI_API_KEY (or GOOGLE_API_KEY) is not configured in environment variables. "
                "Please configure GEMINI_API_KEY in Render Environment Variables (from https://aistudio.google.com/apikey)."
            )
        try:
            client = get_gemini_client(key)
            transcript = "\n".join(f'{m["role"]}: {m["content"]}' for m in turns)
            model_name = env("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip()
            content_text = _call_gemini_generate(
                client=client,
                contents=PROMPT + "\nConversation:\n" + transcript,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0),
                model_name=model_name,
            )
            return _normalize_extracted(json.loads(content_text or "{}"), current)
        except Exception as gemini_err:
            logger.warning("Gemini extraction failed (%s); using deterministic extraction fallback.", gemini_err)
            return _normalize_extracted({}, current)

    if provider == "ollama":
        base_url = env("OLLAMA_BASE_URL", DEFAULT_OLLAMA_URL).rstrip("/")
        model = env("OLLAMA_CHAT_MODEL", env("OLLAMA_LLM_MODEL", env("LLM_MODEL", DEFAULT_OLLAMA_MODEL)))
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
                return _normalize_extracted(parsed, current)
        except urllib.error.HTTPError as he:
            if he.code == 404:
                raise RuntimeError(
                    f"Ollama model '{model}' is not available at {base_url}. "
                    f"Please run 'ollama pull {model}'."
                ) from he
            raise RuntimeError(f"Ollama API request failed with HTTP {he.code}: {he.reason}") from he
        except urllib.error.URLError as ue:
            raise ConnectionError(
                f"Ollama server is not reachable at {base_url}. "
                "For local development, ensure Ollama is running ('ollama serve'). "
                "For Render deployment, please switch to Google Gemini or OpenAI in the LLM Provider dropdown."
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
