"""
EstateAI Concierge Backend Application.
Powered by Amazon Bedrock, Amazon S3, and Amazon EC2.
Provides clean REST API endpoints for conversational real-estate concierge,
deterministic property search from structured S3 datasets (CSV, XLSX, JSON),
RAG specification Q&A over architectural PDFs with Titan v2 embeddings & FAISS,
image asset serving, and customer lead capture.
"""

import copy
import logging
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import env, int_env, bool_env
from app.enquiries import save_enquiry
from app.rag.image_assets import format_asset_payload, ingest_image_assets, list_image_assets
from app.rag.retriever import retrieve_relevant_chunks
from app.rag.store import get_vector_store
from app.schemas import ChatRequest, EnquiryRequest, SearchFilters
from app.services.bedrock_service import BedrockService
from app.services.s3_service import S3Service
from app.data_pipeline.structured import (
    load_csv,
    load_excel,
    load_json,
    normalize_records,
    validate_records,
    search_properties,
)

logger = logging.getLogger("estateai.main")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)

# Global in-memory cache of verified structured property records
VERIFIED_PROPERTIES: list[dict[str, Any]] = []


def extract_bhk_config(text: str, fallback_bhk: Optional[int] = None) -> Optional[str]:
    """Helper to detect BHK configuration string from user text."""
    m = re.search(r"\b([1-9]|10)\s*(?:bhk|bed|bedroom)\b", text.lower())
    if m:
        return f"{m.group(1)}BHK"
    if fallback_bhk and 1 <= fallback_bhk <= 10:
        return f"{fallback_bhk}BHK"
    return None


def extract_chennai_location(text: str) -> Optional[str]:
    """Extract recognized Chennai localities from user text."""
    locs = [
        "anna nagar", "velachery", "porur", "guindy", "medavakkam",
        "perungudi", "sholinganallur", "kelambakkam", "navalur", "omr",
        "ecr", "adyar", "t nagar", "besant nagar", "thiruvanmiyur", "kotturpuram"
    ]
    lower = text.lower()
    for loc in locs:
        if loc in lower:
            return loc.title()
    return None


def _rag_to_details(rag_chunks: list[dict[str, Any]], query: str = "") -> list[str]:
    """
    Extracts concise, professional specification details from retrieved document chunks.
    Filters and prioritizes details based on query topic (e.g. bedroom, kitchen, bathroom,
    amenities, flooring, electrical).
    """
    if not rag_chunks:
        return []

    raw_items = []
    for chunk in rag_chunks:
        text = chunk.get("text", "")
        for line in text.splitlines():
            clean = re.sub(r"[*_#`]+", "", line).strip()
            clean = re.sub(r"^[-•*]\s+", "", clean)
            clean = re.sub(r"^\d+\.\s+", "", clean)
            clean = clean.strip()
            if len(clean) >= 6 and not clean.lower().startswith("here are") and not clean.lower().startswith("dataset:"):
                raw_items.append(clean[:130])

    if not raw_items:
        return []

    q_lower = query.lower().strip() if query else ""
    topic_keywords = {
        "bedroom": ["bedroom", "master bed", "guest bed", "wardrobe", "dimension", "dimensions"],
        "kitchen": ["kitchen", "granite", "sink", "utility", "counter", "chimney", "pipe", "gas", "hob"],
        "bathroom": ["bathroom", "toilet", "sanitary", "cp fitting", "shower", "geyser", "kohler", "toto"],
        "living": ["living", "dining", "foyer", "balcony", "deck", "patio", "terrace"],
        "doors_windows": ["door", "window", "frame", "shutter", "hardware", "lock", "upvc", "glass"],
        "flooring": ["flooring", "tile", "tiles", "vitrified", "granite", "marble", "skirting", "wooden"],
        "electrical": ["electrical", "wiring", "wire", "switch", "schneider", "havells", "ac point", "power backup"],
        "amenities": ["amenit", "clubhouse", "swimming", "pool", "gym", "court", "badminton", "indoor"],
        "parking": ["parking", "car park", "ev charging", "driveway", "slot"],
        "plumbing": ["plumbing", "pipe", "drainage", "sewage", "stp", "water supply", "tank"],
    }

    matched_topics = [t for t, kws in topic_keywords.items() if any(kw in q_lower for kw in kws)]
    if matched_topics:
        target_kws = [kw for t in matched_topics for kw in topic_keywords[t]]
        filtered = [item for item in raw_items if any(kw in item.lower() for kw in target_kws)]
        if filtered:
            return filtered[:12]

    return raw_items[:12]


def load_all_structured_data() -> list[dict[str, Any]]:
    """Loads and normalizes all structured property files from S3 or local cache."""
    s3_service = S3Service()
    docs = s3_service.sync_documents()

    all_normalized: list[dict[str, Any]] = []

    for path in docs:
        ext = path.suffix.lower()
        records: list[dict[str, Any]] = []

        if ext == ".csv":
            records = load_csv(path, source_name=path.name)
        elif ext in (".xlsx", ".xls"):
            records = load_excel(path, source_name=path.name)
        elif ext == ".json" and "image_registry" not in path.name:
            records = load_json(path, source_name=path.name)

        if records:
            norm = normalize_records(records, source_name=path.name)
            valid = validate_records(norm)
            all_normalized.extend(valid)

    # Attach verified default image if missing
    for r in all_normalized:
        if not r.get("image_url"):
            bhk_val = r.get("bhk", 2)
            if bhk_val == 2:
                r["image_url"] = "/api/assets/images/Bedroom.jpg"
            elif bhk_val == 3:
                r["image_url"] = "/api/assets/images/bedroom.jpg.2.jpg"
            else:
                r["image_url"] = "/api/assets/images/Bathroom.jpg"

    logger.info("Total verified structured properties loaded: %d", len(all_normalized))
    return all_normalized


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup & background initialization."""
    global VERIFIED_PROPERTIES
    logger.info("Initializing EstateAI Concierge platform...")

    # 1. Ingest local image assets
    ingest_image_assets()

    # 2. Sync and load structured property datasets from S3 / cache
    VERIFIED_PROPERTIES = load_all_structured_data()

    # 3. Synchronize vector store index for PDFs (runs fingerprint check)
    vector_store = get_vector_store()
    try:
        vector_store.sync_all_pdfs()
    except Exception as e:
        logger.warning("PDF indexing deferred or completed with: %s", e)

    yield

    logger.info("Shutting down EstateAI Concierge backend.")


app = FastAPI(
    title="EstateAI Concierge Backend API",
    description="Production-ready real estate concierge powered by Amazon Bedrock, S3, and EC2.",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS Configuration
cors_env = env("CORS_ORIGINS", "").strip()
if not cors_env or cors_env == "*":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    explicit_origins = [x.strip() for x in cors_env.split(",") if x.strip()]
    for def_origin in ["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"]:
        if def_origin not in explicit_origins:
            explicit_origins.append(def_origin)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=explicit_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Static file mount for property photos and floor plans
assets_dir = Path(__file__).resolve().parent.parent / "data" / "assets" / "images"
assets_dir.mkdir(parents=True, exist_ok=True)
app.mount("/api/assets/images", StaticFiles(directory=str(assets_dir)), name="assets_images")


# =============================================================================
# API ROUTES
# =============================================================================

@app.get("/health")
def health():
    """System health check and AWS environment status."""
    return {
        "status": "ok",
        "service": "estateai-concierge-backend",
        "environment": env("APP_ENV", "production"),
        "aws": {
            "region": env("AWS_REGION", "ap-south-1"),
            "bedrock_chat_model": env("BEDROCK_CHAT_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0"),
            "bedrock_embedding_model": env("BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0"),
            "s3_bucket": env("S3_BUCKET_NAME", ""),
        },
        "flags": {
            "enable_athena": bool_env("ENABLE_ATHENA", False),
            "enable_glue": bool_env("ENABLE_GLUE", False),
        },
        "properties_loaded": len(VERIFIED_PROPERTIES),
    }


@app.get("/api/providers")
def get_providers():
    """Returns available AI provider status (Amazon Bedrock)."""
    return {
        "status": "success",
        "active_provider": "bedrock",
        "providers": {
            "bedrock": {
                "name": "Amazon Bedrock",
                "available": True,
                "chat_model": env("BEDROCK_CHAT_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0"),
                "embedding_model": env("BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0"),
            }
        },
    }


@app.get("/api/assets/images")
def get_images(category: Optional[str] = None):
    """Returns accessible image assets with category filtering."""
    assets = list_image_assets()
    if not assets:
        assets = ingest_image_assets()

    if category:
        cat_lower = category.lower().strip()
        filtered = [a for a in assets if a.get("category", "").lower() == cat_lower]
    else:
        filtered = assets

    return {
        "status": "success",
        "count": len(filtered),
        "images": [
            {
                "filename": a.get("filename"),
                "category": a.get("category", "general"),
                "property_name": a.get("property_name", "General Property"),
                "file_type": a.get("file_type", "image/jpeg"),
                "url": f"/api/assets/images/{a.get('filename')}",
            }
            for a in filtered
        ],
    }


@app.get("/api/documents")
def list_documents():
    """Lists indexed architectural documents and structured datasets."""
    s3_service = S3Service()
    cached = s3_service.get_cached_documents()
    
    docs_summary = []
    for p in cached:
        docs_summary.append({
            "source": p.name,
            "extension": p.suffix.lower(),
            "size_bytes": p.stat().st_size if p.exists() else 0,
        })

    return {
        "status": "success",
        "count": len(docs_summary),
        "documents": docs_summary,
    }


@app.post("/api/documents/upload")
async def upload_document(request: Request, filename: Optional[str] = None):
    """Administrative upload for documents to S3 and automated re-indexing."""
    # Sanitize and validate filename
    target_name = filename or request.headers.get("x-filename", "uploaded_doc.pdf")
    target_name = Path(target_name).name  # Prevent path traversal
    
    ext = Path(target_name).suffix.lower()
    if ext not in (".pdf", ".csv", ".xlsx", ".xls", ".json"):
        raise HTTPException(status_code=400, detail=f"Unsupported file format '{ext}'")

    body = await request.body()
    if not body or len(body) > 25 * 1024 * 1024:  # 25 MB limit
        raise HTTPException(status_code=400, detail="Invalid file size (max 25MB).")

    s3_service = S3Service()
    dest = s3_service.cache_dir / target_name
    with open(dest, "wb") as f:
        f.write(body)

    # Upload to S3 if configured
    s3_service.upload_document(dest)

    # Re-index if PDF
    chunks_added = 0
    if ext == ".pdf":
        vector_store = get_vector_store()
        chunks_added = vector_store.sync_all_pdfs(s3_service.cache_dir)
    elif ext in (".csv", ".xlsx", ".json"):
        global VERIFIED_PROPERTIES
        VERIFIED_PROPERTIES = load_all_structured_data()

    return {
        "status": "success",
        "message": "Document processed successfully",
        "filename": target_name,
        "chunks_added": chunks_added,
    }


@app.post("/api/enquiries")
def enquiry(req: EnquiryRequest):
    """Persists customer enquiries and site visit bookings."""
    try:
        eid = save_enquiry(
            name=req.name,
            phone=req.phone,
            property_id=req.property_id,
            message=req.message,
            consent=req.consent,
        )
        return {
            "status": "success",
            "message": "Enquiry submitted successfully. A property specialist will contact you shortly.",
            "enquiry_id": eid,
        }
    except Exception as exc:
        logger.error("Failed to save enquiry: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to save enquiry.")


# =============================================================================
# CHAT ORCHESTRATOR
# =============================================================================

@app.post("/api/chat")
def chat(req: ChatRequest):
    """
    Main conversational dispatcher.
    Orchestrates:
    1. Question understanding via Amazon Bedrock.
    2. Deterministic property search over structured S3 data.
    3. Document RAG over architectural PDFs via FAISS + Bedrock Titan v2.
    4. Image asset retrieval.
    5. Grounded response synthesis via Amazon Bedrock Converse API.
    """
    query = req.message.strip()
    history = [m.model_dump() for m in req.history]

    bedrock = BedrockService()

    # 1. Understand Query & Extract Filters
    filters = bedrock.extract_filters(message=query, history=history)
    intent = filters.intent

    logger.info("Chat Query: '%s' -> Intent: %s | Filters: %s", query, intent, filters.model_dump(exclude_none=True))

    # WORKFLOW 1: GREETINGS & GENERAL CONVERSATION
    if intent == "general_question":
        greeting_text = (
            filters.assistant_message or
            "Hello! Welcome to EstateAI Concierge. I can help you search verified properties across Chennai, "
            "review architectural specifications, explore room dimensions, and schedule site visits. "
            "How can I assist you today?"
        )
        return {
            "status": "success",
            "assistant_message": greeting_text,
            "filters": filters.model_dump(),
            "properties": [],
            "images": [],
            "sources": [],
        }

    # WORKFLOW 2: MEDIA / IMAGE REQUESTS
    if intent == "media_request":
        # Detect category (bedroom, living, bathroom, kitchen, balcony)
        q_lower = query.lower()
        cat = None
        for c in ("bedroom", "bathroom", "kitchen", "living", "balcony"):
            if c in q_lower:
                cat = c
                break

        assets_resp = get_images(category=cat)
        matched_images = assets_resp.get("images", [])
        cat_label = f"{cat} " if cat else ""
        return {
            "status": "success",
            "assistant_message": f"Here are the documented {cat_label}photos available from verified properties:",
            "filters": filters.model_dump(),
            "properties": [],
            "images": matched_images,
            "image_filter": cat,
            "sources": [],
        }

    # WORKFLOW 3: CONTACT / ENQUIRY INTENT
    if intent == "contact_request":
        return {
            "status": "success",
            "assistant_message": (
                "I would be delighted to help you schedule a site visit or connect with our relationship manager. "
                "Please click the **Schedule Site Visit** button on any property card or provide your contact details."
            ),
            "filters": filters.model_dump(),
            "properties": [],
            "images": [],
            "sources": [],
        }

    # WORKFLOW 4: PROPERTY SEARCH / DOCUMENT Q&A / COMBINED
    matched_properties: list[dict[str, Any]] = []
    retrieved_chunks: list[dict[str, Any]] = []

    # Check if query is about properties (has BHK, price, location, or search intent)
    is_search = intent in ("property_search", "search_refinement") or filters.bhk is not None or filters.max_price is not None or filters.location is not None

    if is_search:
        matched_properties = search_properties(filters.model_dump(), VERIFIED_PROPERTIES, limit=5)

    # Retrieve relevant document chunks for specifications or questions
    bhk_hint = filters.bhk or extract_bhk_config(query)
    retrieved_chunks = retrieve_relevant_chunks(
        query=query,
        top_k=5,
        bhk=filters.bhk,
    )

    # Attach verified RAG specification details to each property card
    if matched_properties:
        spec_details = _rag_to_details(retrieved_chunks, query=query)
        for p in matched_properties:
            p_details = copy.deepcopy(p.get("details", []))
            # Merge with extracted spec details from verified documents
            for d in spec_details:
                if d not in p_details:
                    p_details.append(d)
            p["details"] = p_details[:10]

    # Synthesize grounded answer via Amazon Bedrock
    assistant_answer = bedrock.generate_grounded_answer(
        query=query,
        retrieved_chunks=retrieved_chunks,
        properties=matched_properties if is_search else None,
        history=history,
    )

    # Format source citations
    citations = []
    seen = set()
    for c in retrieved_chunks:
        src = c.get("source", "Document")
        page = c.get("page", 1)
        citation = f"{src} (Page {page})"
        if citation not in seen:
            seen.add(citation)
            citations.append(citation)

    # If search was conducted but returned zero matching records
    if is_search and not matched_properties:
        loc_str = f" in {filters.location}" if filters.location else ""
        bhk_str = f"{filters.bhk} BHK " if filters.bhk else ""
        price_str = f" within ₹{filters.max_price:,}" if filters.max_price else ""
        assistant_answer = (
            f"I searched our verified property database, but could not find any {bhk_str}properties{loc_str}{price_str}. "
            "Would you like me to broaden the price range or show available options in neighboring Chennai localities?"
        )

    return {
        "status": "success",
        "assistant_message": assistant_answer,
        "filters": filters.model_dump(),
        "properties": matched_properties,
        "images": [],
        "sources": citations,
    }
