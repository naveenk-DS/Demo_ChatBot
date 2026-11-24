"""
Document loader module for the Real Estate AI Chatbot RAG system.
Extracts page-by-page text and metadata from PDF files using PyMuPDF (fitz).
"""

import logging
from pathlib import Path
from typing import Any, Optional, Union

try:
    import fitz  
except ImportError:
    fitz = None

logger = logging.getLogger(__name__)


import re


def extract_document_metadata(file_path: Union[str, Path], first_page_text: str = "") -> dict[str, Any]:
    """
    Dynamically infers document metadata (document_id, property_name, configuration, document_type)
    from filename and text patterns without hardcoding specific property names or configurations.
    """
    path = Path(file_path)
    stem = path.stem
    stem_clean = stem.replace("_", " ")
    lower_stem = stem_clean.lower()
    doc_id = re.sub(r"[^a-zA-Z0-9]+", "_", stem).strip("_").lower() or "doc"
    first_lines = [line.strip() for line in first_page_text.split("\n") if line.strip()][:3]

    # 1. Dynamic Configuration extraction (e.g. 1BHK, 2BHK, 3BHK, 4BHK, Studio, Penthouse, Villa, Plot)
    config_match = re.search(
        r"\b([1-9]\s*BHK|[1-9]\s*RK|Studio|Penthouse|Villa|Duplex|Plot)\b",
        f"{stem_clean} {' '.join(first_lines)}",
        re.IGNORECASE,
    )
    configuration = re.sub(r"\s+", "", config_match.group(1).upper()) if config_match else "general"

    # 2. Dynamic Property/Document Name extraction from delimiter or first heading
    property_name = ""
    parts = re.split(r"[-–—|]", stem_clean)
    if len(parts) > 1:
        candidate = parts[-1].strip()
        if not re.search(r"\b([1-9]\s*BHK|Script|Brochure|Floor\s*Plan)\b", candidate, re.I) and len(candidate) > 2:
            property_name = candidate
        else:
            candidate = parts[0].strip()
            if not re.search(r"\b([1-9]\s*BHK|Script|Brochure|Floor\s*Plan)\b", candidate, re.I) and len(candidate) > 2:
                property_name = candidate

    if not property_name and first_lines:
        dash_split = re.split(r"[-–—|]", first_lines[0])
        if len(dash_split) > 1 and len(dash_split[-1].strip()) > 2:
            property_name = dash_split[-1].strip()
        elif len(first_lines[0]) < 60:
            property_name = first_lines[0]

    if not property_name:
        property_name = re.sub(r"[_\-]+", " ", stem).strip().title()

    # Clean out any developer/builder prefixes like 'Casagrand' or 'Casa grand'
    property_name = re.sub(r"(?i)\bcasa\s*grand\b", "", property_name).strip(" -–—|,")
    if not property_name:
        property_name = re.sub(r"[_\-]+", " ", stem).strip().title()

    # 3. Dynamic Document Type detection
    doc_type = "document"
    for candidate_type in ("brochure", "script", "floor_plan", "specification", "pricing", "handbook", "agreement", "guideline", "policy", "rules"):
        if candidate_type in lower_stem:
            doc_type = candidate_type
            break

    return {
        "document_id": doc_id,
        "property_name": property_name,
        "configuration": configuration,
        "document_type": doc_type,
    }


# Backward-compatibility alias
def extract_property_and_config(filename: str, sample_text: str = "") -> tuple[str, str]:
    meta = extract_document_metadata(filename, sample_text)
    return meta["property_name"], meta["configuration"]


def get_default_pdf_dir() -> Path:
    """
    Dynamically resolves the project's root 'pdf/' directory relative to this file.

    Hierarchy:
        <project_root>/
            pdf/
            backend/
                app/
                    rag/
                        loader.py
    """
    return Path(__file__).resolve().parent.parent.parent.parent / "pdf"


def load_single_pdf(file_path: Union[str, Path]) -> list[dict[str, Any]]:
    """
    Extracts text page-by-page and rich metadata from a single PDF file using PyMuPDF.
    Returns empty list if file cannot be opened or contains no extractable text.
    """
    if fitz is None:
        raise ImportError(
            "PyMuPDF is not installed. Please install it using: python -m pip install pymupdf"
        )

    path = Path(file_path)
    if not path.exists():
        logger.warning("PDF file not found: %s", path)
        return []

    documents: list[dict[str, Any]] = []
    try:
        with fitz.open(path) as doc:
            page_count = len(doc)
            if page_count == 0:
                logger.warning("PDF '%s' has 0 pages", path.name)
                return []

            doc_first_text = doc.load_page(0).get_text("text").strip() if page_count > 0 else ""
            doc_meta = extract_document_metadata(path, doc_first_text)
            doc_prop_name = doc_meta["property_name"]
            doc_config = doc_meta["configuration"]
            doc_id = doc_meta["document_id"]
            doc_type = doc_meta["document_type"]

            extracted_pages = 0
            for page_idx in range(page_count):
                try:
                    page = doc.load_page(page_idx)
                    text = page.get_text("text").strip()
                    if not text:
                        continue

                    page_meta = extract_document_metadata(path, text)
                    prop_name = page_meta["property_name"]
                    config = page_meta["configuration"]
                    final_prop = prop_name if prop_name and prop_name != "Bathroom 2" else doc_prop_name
                    final_config = config if config and config != "general" else doc_config

                    documents.append({
                        "source": path.name,
                        "document_id": doc_id,
                        "page": page_idx + 1,
                        "text": text,
                        "property_name": final_prop,
                        "configuration": final_config,
                        "document_type": doc_type,
                    })
                    extracted_pages += 1
                except Exception as page_err:
                    logger.warning("Error extracting page %d from '%s': %s", page_idx + 1, path.name, page_err)

            logger.info("Extracted %d valid page(s) from '%s' (total pages in doc: %d)", extracted_pages, path.name, page_count)
            return documents
    except Exception as file_err:
        logger.error("Failed to read PDF file '%s': %s", path.name, file_err)
        return []


def load_pdf_documents(pdf_dir: Optional[Union[str, Path]] = None) -> list[dict[str, Any]]:
    """
    Loads and extracts text page-by-page from all PDF files in the target directory.
    """
    target_dir = Path(pdf_dir).resolve() if pdf_dir else get_default_pdf_dir()

    if not target_dir.exists():
        logger.warning("PDF directory does not exist: %s", target_dir)
        return []

    if not target_dir.is_dir():
        logger.warning("Specified PDF path is not a directory: %s", target_dir)
        return []

    supported_extensions = ("*.pdf", "*.txt", "*.md")
    all_files = []
    for ext in supported_extensions:
        all_files.extend(target_dir.glob(ext))
    all_files = sorted(all_files, key=lambda p: p.name.lower())

    if not all_files:
        logger.warning("No supported files (*.pdf, *.txt, *.md) found in directory: %s", target_dir)
        return []

    logger.info("Found %d document file(s) in %s", len(all_files), target_dir)
    documents: list[dict[str, Any]] = []

    for file_path in all_files:
        ext = file_path.suffix.lower()
        if ext in (".txt", ".md"):
            try:
                text_content = file_path.read_text(encoding="utf-8", errors="replace").strip()
                if not text_content:
                    continue
                meta = extract_document_metadata(file_path, text_content[:500])
                documents.append({
                    "source": file_path.name,
                    "document_id": meta["document_id"],
                    "page": 1,
                    "text": text_content,
                    "property_name": meta["property_name"],
                    "configuration": meta["configuration"],
                    "document_type": meta["document_type"] or "document",
                })
            except Exception as txt_err:
                logger.error("Failed to read text file '%s': %s", file_path.name, txt_err)
            continue

        docs = load_single_pdf(file_path)
        documents.extend(docs)

    logger.info("Total extracted pages across all PDFs: %d", len(documents))
    return documents


def load_csv_documents(data_dir: Optional[Union[str, Path]] = None) -> list[dict[str, Any]]:
    """
    Loads and extracts structured text records from all CSV files in the target directory.
    Preserves dataset structure and attributes without modifying PDF ingestion.
    """
    import csv

    target_dir = Path(data_dir).resolve() if data_dir else get_default_pdf_dir()
    if not target_dir.exists() or not target_dir.is_dir():
        return []

    csv_files = sorted(target_dir.glob("*.csv"))
    documents: list[dict[str, Any]] = []

    for file_path in csv_files:
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                dataset_name = file_path.stem.replace("_", " ").title()

                for row_idx, row in enumerate(reader, start=1):
                    parts = [f"{k.strip()}: {v.strip()}" for k, v in row.items() if v and v.strip()]
                    row_text = f"Dataset: {dataset_name} | Record #{row_idx}\n" + ", ".join(parts)
                    config = f"{row.get('bedrooms', '')}BHK" if row.get('bedrooms') else "general"

                    documents.append({
                        "source": file_path.name,
                        "page": row_idx,
                        "text": row_text,
                        "property_name": dataset_name,
                        "configuration": config,
                    })
        except Exception as e:
            logger.error("Failed to read CSV file '%s': %s", file_path.name, e)

    return documents


def load_all_documents(target_dir: Optional[Union[str, Path]] = None) -> list[dict[str, Any]]:
    """Loads all text-based documents (PDF and CSV) from the target directory."""
    docs = load_pdf_documents(target_dir)
    docs.extend(load_csv_documents(target_dir))
    return docs
