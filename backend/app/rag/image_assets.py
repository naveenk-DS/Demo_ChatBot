"""
Plain Image Asset Ingestion and Management Module.
Tracks and stores image assets (JPG, JPEG, PNG, WEBP) alongside property documents
without converting them into text chunks, embeddings, or passing them to the LLM.
"""

from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import re
import shutil
from typing import Any, Optional, Union

from .loader import get_default_pdf_dir, extract_document_metadata

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

ROOM_CATEGORIES = {
    "bedroom": ["bedroom", "bed", "master bedroom", "master", "guest room", "kids room"],
    "bathroom": ["bathroom", "bath", "toilet", "washroom", "restroom"],
    "kitchen": ["kitchen", "utility", "pantry", "cooking"],
    "living": ["living", "hall", "lounge", "drawing"],
    "dining": ["dining"],
    "balcony": ["balcony", "deck", "terrace", "verandah", "patio"],
    "entrance": ["entrance", "foyer", "main door", "door"],
    "exterior": ["elevation", "exterior", "building", "facade", "landscape", "front"],
    "floor_plan": ["floor plan", "plan", "layout"],
}


def get_default_assets_dir() -> Path:
    """
    Dynamically resolves the local image asset storage directory:
    <project_root>/backend/data/assets/images/
    """
    base_dir = Path(__file__).resolve().parent.parent.parent / "data" / "assets" / "images"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def get_registry_path() -> Path:
    """
    Dynamically resolves the JSON metadata registry path:
    <project_root>/backend/data/assets/image_registry.json
    """
    registry_file = Path(__file__).resolve().parent.parent.parent / "data" / "assets" / "image_registry.json"
    registry_file.parent.mkdir(parents=True, exist_ok=True)
    return registry_file


def is_supported_image(file_path: Union[str, Path]) -> bool:
    """Checks if a file has a supported image extension (.jpg, .jpeg, .png, .webp)."""
    path = Path(file_path)
    suffix = path.suffix.lower()
    return suffix in SUPPORTED_IMAGE_EXTENSIONS


def detect_image_category(filename: str) -> str:
    """Infers room or feature category from image filename without vision AI."""
    lower_name = filename.lower()
    for category, keywords in ROOM_CATEGORIES.items():
        if any(kw in lower_name for kw in keywords):
            return category
    return "general"


def sanitize_property_name(name: Optional[str]) -> str:
    """Removes any developer prefix like 'Casagrand' or 'Casa grand' from project titles."""
    if not name:
        return "General Property"
    cleaned = re.sub(r"(?i)\bcasa\s*grand\b", "", name).strip(" -–—|,")
    return cleaned if cleaned else "General Property"


def detect_associated_metadata(source_dir: Path) -> dict[str, Any]:
    """
    Inspects neighboring PDF and CSV files in the source directory to discover
    associated property names and document references.
    """
    property_names = set()
    associated_docs = []

    # 1. Discover PDFs
    for pdf_file in source_dir.glob("*.pdf"):
        associated_docs.append(pdf_file.name)
        meta = extract_document_metadata(pdf_file)
        if meta.get("property_name"):
            clean_name = sanitize_property_name(meta["property_name"])
            if clean_name:
                property_names.add(clean_name)

    # 2. Discover CSV/Excel files
    for csv_file in source_dir.glob("*.csv"):
        associated_docs.append(csv_file.name)
        # Use stem as dataset identifier
        dataset_name = sanitize_property_name(csv_file.stem.replace("_", " ").title())
        if dataset_name:
            property_names.add(dataset_name)

    for xls_file in list(source_dir.glob("*.xlsx")) + list(source_dir.glob("*.xls")):
        associated_docs.append(xls_file.name)

    real_projects = [
        p for p in property_names
        if not re.search(r"\b(Sample|Script|Document|Data|Housing)\b", p, re.I)
    ]
    if real_projects:
        primary_property = sorted(real_projects)[0]
    elif property_names:
        primary_property = sorted(list(property_names))[0]
    else:
        primary_property = "General Property"

    return {
        "property_name": sanitize_property_name(primary_property),
        "all_properties": sorted(list(property_names)),
        "associated_documents": sorted(associated_docs),
    }


def load_registry() -> list[dict[str, Any]]:
    """Loads existing image registry from disk."""
    reg_path = get_registry_path()
    if not reg_path.exists():
        return []
    try:
        with open(reg_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        logger.warning("Failed to read image registry: %s", e)
        return []


def save_registry(records: list[dict[str, Any]]) -> None:
    """Saves updated image registry to disk."""
    reg_path = get_registry_path()
    try:
        with open(reg_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)
    except Exception as e:
        logger.error("Failed to save image registry: %s", e)


def ingest_image_assets(
    source_dir: Optional[Union[str, Path]] = None,
    target_dir: Optional[Union[str, Path]] = None,
) -> list[dict[str, Any]]:
    """
    Discovers, stores, and registers plain image files from source directory.

    Rules:
    - Never generates text chunks or embeddings.
    - Never invokes vision models or OCR.
    - Associates images with property metadata from neighboring PDFs or CSVs.
    - Stores images in backend/data/assets/images/.
    - Persists metadata in backend/data/assets/image_registry.json.

    Args:
        source_dir: Path to directory containing uploaded assets (defaults to project's pdf/ folder).
        target_dir: Destination folder for local assets (defaults to backend/data/assets/images/).

    Returns:
        List of ingested image asset metadata records.
    """
    src = Path(source_dir).resolve() if source_dir else get_default_pdf_dir()
    dst = Path(target_dir).resolve() if target_dir else get_default_assets_dir()
    dst.mkdir(parents=True, exist_ok=True)

    if not src.exists() or not src.is_dir():
        logger.warning("Source directory does not exist or is not a directory: %s", src)
        return []

    # Detect context from neighboring documents in the same folder
    context = detect_associated_metadata(src)

    # Find all supported image files
    image_files = [f for f in sorted(src.iterdir()) if f.is_file() and is_supported_image(f)]
    if not image_files:
        logger.info("No supported image files found in %s", src)
        return []

    existing_records = {r.get("filename"): r for r in load_registry()}
    new_records: list[dict[str, Any]] = []

    for img_path in image_files:
        filename = img_path.name
        dest_path = dst / filename

        # Copy image file to assets directory (preserves metadata/timestamps)
        try:
            if not dest_path.exists() or img_path.stat().st_mtime > dest_path.stat().st_mtime:
                shutil.copy2(img_path, dest_path)
        except Exception as copy_err:
            logger.error("Failed to copy image asset '%s' to '%s': %s", filename, dest_path, copy_err)

        category = detect_image_category(filename)
        suffix = img_path.suffix.lower()
        file_type = MIME_TYPES.get(suffix, "image/jpeg")
        file_size = img_path.stat().st_size

        # Configuration match in filename (e.g. 2BHK_Bedroom.jpg)
        config_match = re.search(r"\b([1-9]\s*BHK|[1-9]\s*RK|Studio|Penthouse|Villa)\b", filename, re.IGNORECASE)
        configuration = config_match.group(1).upper().replace(" ", "") if config_match else "general"

        record = {
            "filename": filename,
            "file_path": str(dest_path),
            "original_path": str(img_path),
            "file_type": file_type,
            "extension": suffix,
            "file_size_bytes": file_size,
            "ingestion_date": datetime.now(timezone.utc).isoformat(),
            "category": category,
            "property_name": context.get("property_name", "General Property"),
            "configuration": configuration,
            "associated_documents": context.get("associated_documents", []),
        }

        existing_records[filename] = record
        new_records.append(record)
        logger.info("Ingested image asset: %s (Category: %s, Property: %s)", filename, category, context.get("property_name"))

    all_records = list(existing_records.values())
    save_registry(all_records)
    return all_records


def list_image_assets(
    category: Optional[str] = None,
    property_name: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Retrieves tracked image asset metadata, optionally filtered by category or property."""
    records = load_registry()
    if category:
        cat_lower = category.strip().lower()
        records = [r for r in records if r.get("category", "").lower() == cat_lower]
    if property_name:
        prop_lower = property_name.strip().lower()
        records = [r for r in records if prop_lower in r.get("property_name", "").lower()]
    return records


def format_asset_payload(record: dict[str, Any]) -> dict[str, Any]:
    """Helper to convert stored record to JSON payload with API URL."""
    prop_name = sanitize_property_name(record.get("property_name", "General Property"))
    return {
        "filename": record.get("filename"),
        "category": record.get("category", "general"),
        "property_name": prop_name,
        "file_type": record.get("file_type", "image/jpeg"),
        "file_size_bytes": record.get("file_size_bytes", 0),
        "url": f"/api/assets/images/{record.get('filename')}",
    }


def search_image_assets(
    query: str,
    property_name: Optional[str] = None,
    history: Optional[list[dict[str, str]]] = None,
) -> dict[str, Any]:
    """
    Dynamically searches, filters, and formats local image assets based on the user's chat query and conversation history.

    Adheres strictly to constraints:
    - No OCR, no vision AI, no caption generation, no LLM image analysis.
    - Matches dynamically against registered categories, metadata, and filenames.
    - If user asks for all property images, returns all available images for that context.
    - If a specific category is requested, returns ONLY matching images.
    - If the user refers to images contextually ("show the image", "show that room", "show it"),
      infers the room category from the immediately preceding conversation context.
    - If the previous topic is ambiguous, asks a short clarification instead of showing unrelated images.
    """
    records = list_image_assets()
    if not records:
        records = ingest_image_assets()

    total_available = len(records)
    available_categories = sorted(list({
        r.get("category", "").title()
        for r in records
        if r.get("category") and r.get("category").lower() != "general"
    }))

    raw_query = query.strip().lower()

    # 1. Detect if user is asking for ALL images
    all_indicators = [
        "property image", "property images", "all property images", "all images",
        "show me images", "show me the images", "show images", "show all images",
        "show photos", "all photos", "property photos", "show all property photos",
        "reset gallery", "reset images", "view all images", "view all", "show all"
    ]
    # Check if query is just asking for images in general
    clean_q = re.sub(r"[^\w\s]", " ", raw_query)
    clean_q = re.sub(r"\s+", " ", clean_q).strip()

    is_all = any(indicator in raw_query for indicator in all_indicators) or clean_q in (
        "show me the property images", "show me property images", "show property images",
        "show me images", "show images", "images", "photos", "pictures",
        "show me the images", "display all images", "show all"
    )

    if is_all:
        matched = records
        if property_name:
            prop_lower = property_name.strip().lower()
            prop_matched = [r for r in records if prop_lower in r.get("property_name", "").lower()]
            if prop_matched:
                matched = prop_matched

        formatted_images = [format_asset_payload(r) for r in matched]
        return {
            "images": formatted_images,
            "category": "all",
            "display_name": "All Property Images",
            "is_all": True,
            "is_filtered": False,
            "matched_count": len(formatted_images),
            "total_available": total_available,
            "available_categories": available_categories,
            "assistant_message": (
                f"Displaying all {len(formatted_images)} property image(s) in the right-side media panel. "
                f"You can click any thumbnail to preview it, or ask for specific areas such as bathroom or bedroom."
            ),
        }

    # 2. Extract requested category / room
    target_category: Optional[str] = None
    target_keywords: list[str] = []
    display_name = ""

    # Check known room categories and their aliases
    # Check master bedroom first to be specific
    if "master bedroom" in raw_query or "master bed" in raw_query:
        target_category = "bedroom"
        target_keywords = ["master bedroom", "master", "bedroom", "bed"]
        display_name = "Master Bedroom"
    else:
        for cat, keywords in ROOM_CATEGORIES.items():
            for kw in keywords:
                # Check for whole word match
                if re.search(rf"\b{re.escape(kw)}\b", raw_query):
                    target_category = cat
                    target_keywords = keywords
                    display_name = cat.title()
                    break
            if target_category:
                break

    # If not found in current query, check dynamically against all categories registered in existing images
    if not target_category:
        for r in records:
            cat = r.get("category", "").lower()
            if cat and cat != "general" and re.search(rf"\b{re.escape(cat)}\b", raw_query):
                target_category = cat
                target_keywords = [cat]
                display_name = cat.title()
                break

    # If still not found, try extracting candidate noun from "show [noun]" or "images of [noun]"
    if not target_category:
        match_phrase = re.search(
            r"(?:show(?:\s+me)?|view|display|pictures? of|photos? of|images? of)\s+(?:the\s+)?([a-z0-9_\-]+)",
            raw_query
        )
        if match_phrase:
            extracted = match_phrase.group(1).strip()
            if extracted not in ("images", "image", "photos", "photo", "pictures", "picture", "the", "me", "a", "an", "it", "that", "this"):
                target_category = extracted
                target_keywords = [extracted]
                display_name = extracted.title()

    # Context-aware inference from conversation history when user makes an implicit reference
    is_implicit_request = not target_category and (
        any(k in raw_query for k in ["image", "images", "photo", "photos", "picture", "pictures"])
        or any(phrase in raw_query for phrase in ["that room", "this room", "the room", "show it", "show that", "show me that", "see it", "view it", "display it"])
        or clean_q in ("show me", "can you show", "can i see", "show", "display", "view", "show it", "show that", "show that room")
    )

    if not target_category and history:
        # Helper to detect unique room categories mentioned in a text block
        def _extract_categories_from_text(text: str) -> list[tuple[str, list[str]]]:
            if not text:
                return []
            found = []
            lower_text = text.lower()
            for cat, keywords in ROOM_CATEGORIES.items():
                if any(re.search(rf"\b{re.escape(kw)}\b", lower_text) for kw in keywords):
                    found.append((cat, keywords))
            return found

        prev_user_msgs = [m.get("content", "") for m in history if m.get("role") == "user"]
        prev_asst_msgs = [m.get("content", "") for m in history if m.get("role") == "assistant"]

        last_user_text = prev_user_msgs[-1] if prev_user_msgs else ""
        last_asst_text = prev_asst_msgs[-1] if prev_asst_msgs else ""

        # Step A: Check if the immediately preceding user query explicitly focused on a specific room
        user_cats = _extract_categories_from_text(last_user_text)
        if len(user_cats) == 1:
            target_category, target_keywords = user_cats[0]
            display_name = target_category.title()
            logger.info("Contextual image retrieval inferred category '%s' from previous user query: '%s'", display_name, last_user_text)
        elif len(user_cats) == 0:
            # Step B: Check the assistant's previous response
            asst_cats = _extract_categories_from_text(last_asst_text)
            if len(asst_cats) == 1:
                target_category, target_keywords = asst_cats[0]
                display_name = target_category.title()
                logger.info("Contextual image retrieval inferred category '%s' from previous assistant message.", display_name)
            elif len(asst_cats) > 1 and is_implicit_request:
                # Ambiguous: multiple rooms were discussed across the whole unit
                avail_str = " or ".join(available_categories) if available_categories else "Bedroom or Bathroom"
                return {
                    "images": [],
                    "category": None,
                    "display_name": "Clarification",
                    "is_all": False,
                    "is_filtered": False,
                    "matched_count": 0,
                    "total_available": total_available,
                    "available_categories": available_categories,
                    "assistant_message": f"Which room or area would you like to see? I can display images for {avail_str}.",
                }
        elif len(user_cats) > 1 and is_implicit_request:
            # Ambiguous: user previously asked about multiple rooms
            cats_str = " or ".join([c[0].title() for c in user_cats])
            return {
                "images": [],
                "category": None,
                "display_name": "Clarification",
                "is_all": False,
                "is_filtered": False,
                "matched_count": 0,
                "total_available": total_available,
                "available_categories": available_categories,
                "assistant_message": f"Which room would you like to see? You can choose from {cats_str}.",
            }

    # If still not determined and it's an implicit request with no prior room context
    if not target_category and is_implicit_request:
        avail_str = " or ".join(available_categories) if available_categories else "Bedroom or Bathroom"
        return {
            "images": [],
            "category": None,
            "display_name": "Clarification",
            "is_all": False,
            "is_filtered": False,
            "matched_count": 0,
            "total_available": total_available,
            "available_categories": available_categories,
            "assistant_message": f"Which room or area would you like to see? Currently available categories include: {avail_str}.",
        }

    # Fallback to general if nothing could be determined
    if not target_category:
        target_category = "general"
        target_keywords = ["image", "photo"]
        display_name = "Requested"

    # 3. Match against records using categories, filenames, and metadata
    matched = []
    for r in records:
        r_cat = r.get("category", "").lower()
        r_fname = r.get("filename", "").lower()
        r_config = r.get("configuration", "").lower()
        r_prop = r.get("property_name", "").lower()

        # Category match
        cat_match = (r_cat == target_category) or any(kw in r_cat for kw in target_keywords)

        # Filename match (e.g. "bedroom.jpg", "Bathroom.jpg")
        fname_match = any(re.search(rf"\b{re.escape(kw)}\b", r_fname) or kw in r_fname for kw in target_keywords)

        # Config match
        config_match = any(kw in r_config for kw in target_keywords)

        if cat_match or fname_match or config_match:
            if property_name and property_name.strip().lower() not in r_prop:
                continue
            matched.append(r)

    formatted_images = [format_asset_payload(r) for r in matched]

    # 4. Formulate response
    if formatted_images:
        msg = (
            f"I've displayed the matching {display_name} image(s) ({len(formatted_images)} found) "
            f"in the right-side media panel. You can click on any thumbnail for a full-size preview."
        )
    else:
        avail_str = ", ".join(available_categories) if available_categories else "None"
        msg = (
            f"There are currently no {display_name} images available in the local property assets. "
            f"Currently available categories in the gallery include: {avail_str}. "
            f"You can ask to view any of those or request to show all property images."
        )

    return {
        "images": formatted_images,
        "category": target_category,
        "display_name": display_name,
        "is_all": False,
        "is_filtered": True,
        "matched_count": len(formatted_images),
        "total_available": total_available,
        "available_categories": available_categories,
        "assistant_message": msg,
    }


def get_image_status_message(query: str = "") -> str:
    """
    Constructs an honest, compliant response when users ask about images.
    Adheres strictly to requirement:
    'images are stored as assets but are not currently analyzed by AI.'
    """
    images = list_image_assets()
    if not images:
        # Check source dir if not yet ingested
        images = ingest_image_assets()

    if images:
        names = [f"**{img['filename']}** ({img.get('category', 'general').title()})" for img in images]
        summary_list = ", ".join(names[:5])
        suffix = f" (and {len(names) - 5} more)" if len(names) > 5 else ""
        return (
            f"Property image files ({summary_list}{suffix}) are stored locally as plain image assets, "
            f"but they are not currently analyzed by AI (vision and visual analysis are disabled in this demo). "
            f"However, detailed room dimensions, floor plans, and architectural specifications are available "
            f"from the official property documentation."
        )

    return (
        "Property images are stored locally as plain assets but are not currently analyzed by AI. "
        "No images are currently registered for this property. "
        "All specifications and floor details are available from the official documents."
    )

