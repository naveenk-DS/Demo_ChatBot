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
    return os.getenv(name, default)

def int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default
