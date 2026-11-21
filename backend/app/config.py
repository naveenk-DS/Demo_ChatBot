import os
from pathlib import Path
from dotenv import load_dotenv

# Automatically load from backend/.env if present
_backend_env = Path(__file__).resolve().parents[1] / ".env"
if _backend_env.exists():
    load_dotenv(_backend_env, override=False)

# Automatically load from project root .env if present
_root_env = Path(__file__).resolve().parents[2] / ".env"
if _root_env.exists():
    load_dotenv(_root_env, override=False)

# Fallback default load
load_dotenv(override=False)

def env(name: str, default: str = "") -> str:
    val = os.getenv(name)
    if val is not None and val.strip():
        return val.strip()
    # Support common alternative environment variable names
    if name == "GEMINI_API_KEY":
        alt = os.getenv("GOOGLE_API_KEY")
        if alt is not None and alt.strip():
            return alt.strip()
    if name == "GEMINI_MODEL":
        alt = os.getenv("GOOGLE_MODEL")
        if alt is not None and alt.strip():
            return alt.strip()
    return default

def int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default
