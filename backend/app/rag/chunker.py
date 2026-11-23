"""
Text chunking module for the Real Estate AI Chatbot RAG system.
Scalable, document-agnostic semantic chunker that automatically discovers section
headers, room boundaries, dimensions, and categories across any real estate PDF.
"""

import logging
from pathlib import Path
import re
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE: int = 600
DEFAULT_CHUNK_OVERLAP: int = 100

# Document-agnostic section header detection:
# Matches lines starting with a capital letter/digit, up to 45 characters, ending with a colon
# OR appearing as a section title line immediately preceding bullet points (e.g. "Master Bedroom\n• ...").
# E.g. "Entrance:", "Living & Dining:", "Kitchen:", "Master Bedroom:", "Specifications:", "Amenities:"
GENERIC_HEADER_REGEX = re.compile(
    r"(?=^[A-Z0-9][A-Za-z0-9\s&,/()-]{1,45}(?::|\s*$)(?=\s*\n\s*•))|(?=^[A-Z0-9][A-Za-z0-9\s&,/()-]{1,45}:\s*$)",
    re.MULTILINE,
)

# Generic real-estate category taxonomy
REAL_ESTATE_TAXONOMY = {
    "entrance": ("entrance", "foyer", "main door", "lobby", "gateway", "entry", "reception"),
    "living_dining": ("living", "dining", "drawing", "hall", "lounge", "family room"),
    "kitchen": ("kitchen", "utility", "pantry", "sink", "cooktop", "countertop"),
    "bedroom": ("bedroom", "master bed", "guest bed", "suite", "bed 2", "bed 3", "king size bed"),
    "bathroom": ("bathroom", "toilet", "washroom", "powder room", "shower", "bath 2", "sanitary"),
    "balcony": ("balcony", "terrace", "deck", "patio", "verandah"),
    "flooring": ("flooring", "tile", "vitrified", "marble", "wooden floor", "granite"),
    "electrical": ("electrical", "switch", "socket", "wiring", "lighting", "power"),
    "amenities": ("amenit", "clubhouse", "gym", "swimming", "park", "court", "garden", "play area"),
    "specifications": ("specification", "fittings", "plumbing", "doors & windows", "finish", "structure"),
}


def _sanitize_name(name: str) -> str:
    """Converts a filename or string into a clean, deterministic identifier."""
    stem = Path(name).stem
    sanitized = re.sub(r"[^a-zA-Z0-9]+", "_", stem).strip("_").lower()
    return sanitized or "doc"


def detect_category(heading: str, content: str = "") -> str:
    """
    Classifies a text block into a real estate domain category using semantic keyword matching.
    Returns 'general' if no specific category can be confidently identified.
    """
    h_lower = heading.lower()
    c_lower = content.lower()

    # 1. Primary check: match against heading
    for category, keywords in REAL_ESTATE_TAXONOMY.items():
        if any(kw in h_lower for kw in keywords):
            return category

    # 2. Secondary check: match against content
    for category, keywords in REAL_ESTATE_TAXONOMY.items():
        if any(kw in c_lower for kw in keywords):
            return category

    return "general"


def _find_split_point(text: str, start: int, ideal_end: int) -> int:
    """
    Finds a natural split boundary near ideal_end while protecting measurements and lists.
    """
    if ideal_end >= len(text):
        return len(text)

    search_start = max(start + 100, ideal_end - 150)
    window = text[search_start:ideal_end]

    # Boundary 1: Paragraph break
    pos = window.rfind("\n\n")
    if pos != -1:
        return search_start + pos + 2

    # Boundary 2: Line break / bullet point
    pos = window.rfind("\n")
    if pos != -1:
        return search_start + pos + 1

    # Boundary 3: Sentence boundary followed by whitespace
    for punct in (". ", "! ", "? "):
        pos = window.rfind(punct)
        if pos != -1:
            return search_start + pos + 2

    # Boundary 4: Word boundary
    pos = window.rfind(" ")
    if pos != -1:
        return search_start + pos + 1

    return ideal_end


def _split_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Splits text into chunks of approximately chunk_size with chunk_overlap."""
    if chunk_size <= 0:
        raise ValueError(f"chunk_size must be greater than 0, got {chunk_size}")
    if chunk_overlap < 0:
        raise ValueError(f"chunk_overlap must be greater than or equal to 0, got {chunk_overlap}")
    if chunk_overlap >= chunk_size:
        raise ValueError(
            f"chunk_overlap ({chunk_overlap}) must be strictly smaller than chunk_size ({chunk_size})"
        )

    cleaned = text.strip()
    if not cleaned:
        return []

    if len(cleaned) <= chunk_size:
        return [cleaned]

    chunks: list[str] = []
    start = 0
    text_len = len(cleaned)

    while start < text_len:
        ideal_end = start + chunk_size
        end = _find_split_point(cleaned, start, ideal_end)

        if end <= start:
            end = min(start + chunk_size, text_len)

        chunk = cleaned[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= text_len:
            break

        next_start = end - chunk_overlap
        if next_start <= start:
            next_start = end

        start = next_start

    return chunks


def chunk_documents(
    documents: list[dict[str, Any]],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    structured: bool = True,
) -> list[dict[str, Any]]:
    """
    Splits page-level documents into semantic chunks.
    Fully document-agnostic: handles any PDF without hardcoded property names.

    Args:
        documents: List of page dictionaries from loader.py.
        chunk_size: Target character length per chunk (default: 600).
        chunk_overlap: Target character overlap between consecutive chunks (default: 100).
        structured: If True (default), aligns chunks to section headers with dynamic metadata.
                    If False, uses character sliding window.

    Returns:
        List of chunk dictionaries with rich metadata.
    """
    if chunk_size <= 0:
        raise ValueError(f"chunk_size must be greater than 0, got {chunk_size}")
    if chunk_overlap < 0:
        raise ValueError(f"chunk_overlap must be greater than or equal to 0, got {chunk_overlap}")
    if chunk_overlap >= chunk_size:
        raise ValueError(
            f"chunk_overlap ({chunk_overlap}) must be strictly smaller than chunk_size ({chunk_size})"
        )

    if not documents:
        logger.warning("No documents provided to chunk_documents().")
        return []

    all_chunks: list[dict[str, Any]] = []

    # Track section continuity across pages of the same source document
    last_source = None
    last_section_heading = "Overview"

    for doc in documents:
        source = doc.get("source", "unknown")
        page = int(doc.get("page", 1))
        raw_text = doc.get("text", "").strip()

        if not raw_text:
            continue

        if source != last_source:
            last_source = source
            last_section_heading = "Overview"

        doc_prefix = _sanitize_name(source)
        prop_name = doc.get("property_name", "General Property")
        config = doc.get("configuration", "general")

        if structured:
            # Handle text continuation if a page begins immediately with bullet points
            processed_text = raw_text
            if raw_text.startswith("•") and last_section_heading and last_section_heading != "Overview":
                processed_text = f"{last_section_heading} (continued):\n{raw_text}"

            sections = GENERIC_HEADER_REGEX.split(processed_text)
            chunk_idx = 1

            for section in sections:
                cleaned_sec = section.strip()
                if not cleaned_sec:
                    continue

                # Determine section heading dynamically
                first_line = cleaned_sec.split("\n")[0].strip()
                if first_line.endswith(":") or (len(first_line) <= 45 and not first_line.startswith("•")):
                    heading = first_line.rstrip(":")
                    last_section_heading = heading
                else:
                    heading = last_section_heading

                category = detect_category(heading, cleaned_sec)

                # Keep coherent section intact if reasonable size, else split safely
                if len(cleaned_sec) <= chunk_size + 150:
                    chunk_id = f"{doc_prefix}_p{page}_c{chunk_idx}_{category}"
                    chunk_idx += 1
                    all_chunks.append({
                        "chunk_id": chunk_id,
                        "source": source,
                        "page": page,
                        "property_name": prop_name,
                        "configuration": config,
                        "category": category,
                        "text": cleaned_sec,
                        "char_count": len(cleaned_sec),
                    })
                else:
                    splits = _split_text(cleaned_sec, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
                    for split_text in splits:
                        chunk_id = f"{doc_prefix}_p{page}_c{chunk_idx}_{category}"
                        chunk_idx += 1
                        all_chunks.append({
                            "chunk_id": chunk_id,
                            "source": source,
                            "page": page,
                            "property_name": prop_name,
                            "configuration": config,
                            "category": category,
                            "text": split_text,
                            "char_count": len(split_text),
                        })
        else:
            # Fallback legacy sliding window
            text_splits = _split_text(raw_text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
            for chunk_num, split_text in enumerate(text_splits, start=1):
                chunk_id = f"{doc_prefix}_p{page}_c{chunk_num}"
                all_chunks.append({
                    "chunk_id": chunk_id,
                    "source": source,
                    "page": page,
                    "property_name": prop_name,
                    "configuration": config,
                    "category": "general",
                    "text": split_text,
                    "char_count": len(split_text),
                })

    logger.info(
        "Chunked %d document page(s) into %d chunks (structured=%s).",
        len(documents),
        len(all_chunks),
        structured,
    )
    return all_chunks


chunk_documents_structured = lambda docs, **kwargs: chunk_documents(docs, structured=True, **kwargs)
