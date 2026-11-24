"""
RAG Package for EstateAI Concierge using Amazon Bedrock and FAISS.
"""

from .loader import load_pdf_documents
from .chunker import chunk_documents
from .store import get_vector_store, FaissVectorStore
from .retriever import (
    hybrid_search,
    retrieve_relevant_chunks,
    DynamicBM25,
)
from .service import answer_question

__all__ = [
    "load_pdf_documents",
    "chunk_documents",
    "get_vector_store",
    "FaissVectorStore",
    "hybrid_search",
    "retrieve_relevant_chunks",
    "DynamicBM25",
    "answer_question",
]
