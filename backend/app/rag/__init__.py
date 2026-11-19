"""
RAG Package for Real Estate AI Chatbot.
"""

from .loader import load_pdf_documents
from .chunker import chunk_documents
from .store import (
    get_vector_store,
    get_or_create_collection,
    add_chunks,
    get_embedding,
    check_ollama_status,
    DEFAULT_COLLECTION_NAME,
    DEFAULT_STRUCTURED_COLLECTION,
)
from .retriever import (
    hybrid_search,
    retrieve_hybrid,
    retrieve_relevant_chunks,
    dense_search,
    bm25_search,
    DynamicBM25,
)

__all__ = [
    "load_pdf_documents",
    "chunk_documents",
    "get_vector_store",
    "get_or_create_collection",
    "add_chunks",
    "get_embedding",
    "check_ollama_status",
    "DEFAULT_COLLECTION_NAME",
    "DEFAULT_STRUCTURED_COLLECTION",
    "hybrid_search",
    "retrieve_hybrid",
    "retrieve_relevant_chunks",
    "dense_search",
    "bm25_search",
    "DynamicBM25",
]
