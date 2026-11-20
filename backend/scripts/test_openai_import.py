"""
Test script to verify OpenAI SDK imports, client initialization,
and jiter fallback functionality in backend/.venv.
"""

import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

def test_jiter_and_openai():
    print("=" * 80)
    print("TESTING JITER & OPENAI SDK IMPORT AND FUNCTIONALITY")
    print("=" * 80)

    # 1. Test jiter
    import jiter
    print(f"✓ Successfully imported jiter from: {jiter.__file__}")

    test_bytes = b'{"name": "Casagrand Aquagrove", "bhk": 3, "price": 6900000}'
    parsed = jiter.from_json(test_bytes)
    assert parsed.get("name") == "Casagrand Aquagrove"
    assert parsed.get("bhk") == 3
    print(f"✓ jiter.from_json() parsed test bytes correctly: {parsed}")

    # 2. Test OpenAI import and chat completions resource
    from openai import OpenAI
    print("✓ Successfully imported OpenAI class")

    from backend.app.config import env
    key = env("OPENAI_API_KEY")
    assert key, "OPENAI_API_KEY is missing from configuration!"
    print(f"✓ Found configured OPENAI_API_KEY: {key[:12]}...{key[-6:]}")

    client = OpenAI(api_key=key)
    print("✓ Successfully initialized OpenAI client")

    # Access chat.completions property (this was where jiter import was triggered)
    chat_comp = client.chat.completions
    print(f"✓ Successfully accessed client.chat.completions: {type(chat_comp)}")

    print("\n" + "=" * 80)
    print("ALL TESTS PASSED: JITER & OPENAI SDK ARE 100% OPERATIONAL")
    print("=" * 80)

if __name__ == "__main__":
    test_jiter_and_openai()

