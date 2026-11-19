import os
from dotenv import load_dotenv
load_dotenv()

def env(name: str, default: str = "") -> str:
    return os.getenv(name, default)

def int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default
