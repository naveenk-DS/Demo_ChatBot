"""
RAG Question-Answering Service for EstateAI.
Delegates grounded answer synthesis to Amazon Bedrock Converse API.
Replaces obsolete Gemini, OpenAI, and Ollama implementations.
"""

import logging
from typing import Any, Optional

from app.rag.retriever import retrieve_relevant_chunks, DEFAULT_TOP_K
from app.services.bedrock_service import BedrockService

logger = logging.getLogger("estateai.rag_service")


def answer_question(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    properties: Optional[list[dict[str, Any]]] = None,
    history: Optional[list[dict[str, str]]] = None,
) -> dict[str, Any]:
    """
    Retrieves verified PDF chunks and synthesizes a grounded answer via Amazon Bedrock.
    """
    bedrock = BedrockService()
    
    # 1. Retrieve relevant document chunks via hybrid search
    chunks = retrieve_relevant_chunks(query, top_k=top_k)
    
    # 2. Synthesize grounded answer
    answer = bedrock.generate_grounded_answer(
        query=query,
        retrieved_chunks=chunks,
        properties=properties,
        history=history,
    )
    
    # 3. Format source citations
    sources = []
    seen = set()
    for c in chunks:
        src = c.get("source", "Document")
        page = c.get("page", 1)
        citation = f"{src} (Page {page})"
        if citation not in seen:
            seen.add(citation)
            sources.append(citation)

    return {
        "status": "success",
        "answer": answer,
        "sources": sources,
        "chunks": chunks,
    }
