"""
LLM Intent and Filter Extraction for EstateAI.
Powered by Amazon Bedrock.
Obsolete OpenAI, Gemini, and Ollama providers removed.
"""

import logging
from typing import Any, Optional

from app.schemas import SearchFilters
from app.services.bedrock_service import BedrockService

logger = logging.getLogger("estateai.llm")


def understand(
    provider: str,
    history: list[dict[str, str]],
    current: str,
) -> SearchFilters:
    """
    Analyzes conversation history and current user query using Amazon Bedrock.
    Extracts structured SearchFilters (intent, BHK, price bounds, location, city).
    """
    bedrock = BedrockService()
    filters = bedrock.extract_filters(message=current, history=history)
    return filters
