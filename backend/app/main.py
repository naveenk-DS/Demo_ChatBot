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

from fastapi import FastAPI, HTTPException, Request, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import env, int_env, bool_env
from app.enquiries import save_enquiry
from app.rag.image_assets import format_asset_payload, ingest_image_assets, list_image_assets
from app.rag.retriever import retrieve_relevant_chunks
from app.rag.store import get_vector_store
from app.schemas import ChatRequest, EnquiryRequest, SearchFilters
from app.services.bedrock_service import BedrockService
from app.services.s3_service import S3Service, S3AccessError, S3PaginationError
from app.services.document_registry import DocumentRegistry, get_document_registry
from app.services.lock_service import acquire_indexing_lock, IndexingConflictError
from app.rag.loader import load_single_pdf
from app.data_pipeline.structured import (
    load_csv,
    load_excel,
    load_json,
    normalize_records,
    validate_records,
    search_properties,
    StructuredDataStore,
    get_structured_store,
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


def require_admin_auth(x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key")):
    """
    Enforces administrative key validation for document uploads and re-indexing.
    If ADMIN_API_KEY is defined in environment, it must match.
    In production mode, if ADMIN_API_KEY is not defined, admin endpoints require non-empty header.
    """
    admin_key = env("ADMIN_API_KEY", "")
    is_prod = env("APP_ENV", "production").lower() in ("production", "prod")
    if admin_key:
        if not x_admin_key or x_admin_key != admin_key:
            raise HTTPException(status_code=401, detail="Unauthorized: Invalid or missing X-Admin-Key header")
    elif is_prod:
        if not x_admin_key:
            raise HTTPException(status_code=401, detail="Unauthorized: Administrative actions require X-Admin-Key in production")


def sync_all_pipeline(force_rebuild: bool = False) -> dict[str, Any]:
    """
    Performs dynamic, incremental synchronization across Amazon S3, Document Registry,
    Structured Data Store, and FAISS Vector Store.
    
    Protected by inter-process and thread locking to prevent concurrent indexing corruption.
    
    Handles:
    - Dynamic discovery of arbitrary number of documents via list_objects_v2 pagination
    - Incremental ingestion of new CSV, XLS, XLSX, JSON, and PDF files
    - Automatic removal of stale records and vector chunks when files are modified or deleted
    - Resilient recovery on EC2 restart
    - Full rebuilding when force_rebuild=True with pre-validation of S3 accessibility
    """
    global VERIFIED_PROPERTIES
    s3_service = S3Service()
    registry = get_document_registry()
    structured_store = get_structured_store()
    vector_store = get_vector_store()
    bedrock = BedrockService()

    with acquire_indexing_lock(timeout_seconds=30.0):
        if force_rebuild:
            # S3 failure safety: verify S3 is reachable and accessible BEFORE wiping local data
            if s3_service.is_s3_configured():
                try:
                    s3_service.list_remote_documents()
                except Exception as s3_err:
                    logger.error("Force rebuild aborted: unable to access S3: %s", s3_err)
                    raise S3AccessError(f"Cannot force rebuild: S3 access failure ({s3_err})") from s3_err

            logger.info("Executing full pipeline rebuild: purging structured records, vector index, and registry cache.")
            structured_store.clear()
            vector_store.clear_all()
            registry.clear()

        logger.info("Executing incremental document synchronization pipeline...")
        sync_manifest = s3_service.sync_documents_incremental(registry)

        # 1. Handle deleted documents (purge from structured store & FAISS)
        for deleted_key in sync_manifest["deleted"]:
            filename = Path(deleted_key).name
            ext = Path(filename).suffix.lower()

            if ext in (".csv", ".xlsx", ".xls", ".json"):
                purged = structured_store.remove(filename)
                logger.info("Purged %d structured record(s) for deleted file '%s'", purged, filename)
            elif ext == ".pdf":
                purged = vector_store.remove_document(filename)
                logger.info("Purged %d vector chunk(s) for deleted PDF '%s'", purged, filename)

            registry.mark_deleted(deleted_key)

        # 2. Process newly added or modified documents
        targets_to_process = sync_manifest["new"] + sync_manifest["modified"]
        for path in targets_to_process:
            ext = path.suffix.lower()
            filename = path.name
            f_hash = s3_service.compute_file_hash(path)

            registry.update_status(filename, status="processing")

            try:
                if ext in (".csv", ".xlsx", ".xls", ".json"):
                    count = structured_store.add_or_update(path, source_name=filename)
                    registry.update_status(filename, status="indexed", record_count=count, fingerprint=f_hash)
                elif ext == ".pdf":
                    if bedrock.has_credentials():
                        pdf_docs = load_single_pdf(path)
                        chunk_count = vector_store.add_documents(pdf_docs, filename=filename, file_hash=f_hash)
                        if chunk_count > 0:
                            registry.update_status(filename, status="indexed", chunk_count=chunk_count, fingerprint=f_hash)
                        else:
                            registry.update_status(
                                filename,
                                status="failed",
                                fingerprint=f_hash,
                                error_message="Zero valid embeddings generated",
                            )
                    else:
                        registry.update_status(
                            filename,
                            status="pending",
                            fingerprint=f_hash,
                            error_message="Bedrock credentials deferred on local environment",
                        )
            except Exception as proc_err:
                logger.error("Failed processing document '%s': %s", filename, proc_err)
                registry.update_status(filename, status="failed", error_message=str(proc_err))

        # 3. Ensure unchanged structured files are present in memory (e.g. after EC2 reboot)
        for path in sync_manifest["unchanged"]:
            ext = path.suffix.lower()
            filename = path.name
            if ext in (".csv", ".xlsx", ".xls", ".json"):
                if filename not in structured_store.records_by_source:
                    structured_store.add_or_update(path, source_name=filename)

        VERIFIED_PROPERTIES = structured_store.get_all_records()
        logger.info("Sync pipeline complete. Verified properties: %d | Active documents: %d", len(VERIFIED_PROPERTIES), len(registry.list_active()))

        failed_list = sync_manifest["failed"]
        status = "success"
        if failed_list:
            status = "partial_success" if (sync_manifest["new"] or sync_manifest["modified"] or sync_manifest["unchanged"]) else "failed"

        return {
            "status": status,
            "verified_properties": len(VERIFIED_PROPERTIES),
            "manifest": {
                "new": [p.name for p in sync_manifest["new"]],
                "modified": [p.name for p in sync_manifest["modified"]],
                "deleted": sync_manifest["deleted"],
                "unchanged": [p.name for p in sync_manifest["unchanged"]],
                "failed": failed_list,
            },
        }


def load_all_structured_data() -> list[dict[str, Any]]:
    """Backward-compatible loader."""
    sync_all_pipeline()
    return VERIFIED_PROPERTIES


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup & background initialization."""
    logger.info("Initializing EstateAI Concierge platform...")

    # 1. Ingest local image assets
    ingest_image_assets()

    # 2. Run dynamic incremental synchronization
    try:
        sync_all_pipeline()
    except Exception as e:
        logger.error("Initial synchronization failed: %s", e)

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
    registry = get_document_registry()
    active_docs = registry.list_active()
    vector_store = get_vector_store()
    bedrock = BedrockService()
    s3_service = S3Service()
    bedrock_ready = bedrock.has_credentials()
    s3_configured = s3_service.is_s3_configured()
    system_ready = len(VERIFIED_PROPERTIES) > 0 or len(active_docs) > 0 or bedrock_ready

    return {
        "status": "ok",
        "ready": system_ready,
        "service": "estateai-concierge-backend",
        "environment": env("APP_ENV", "production"),
        "aws": {
            "region": env("AWS_REGION", "ap-south-1"),
            "bedrock_ready": bedrock_ready,
            "bedrock_chat_model": env("BEDROCK_MODEL_ID", env("BEDROCK_CHAT_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0")),
            "bedrock_embedding_model": env("BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0"),
            "s3_configured": s3_configured,
            "s3_bucket": env("S3_BUCKET_NAME", ""),
        },
        "flags": {
            "enable_athena": bool_env("ENABLE_ATHENA", False),
            "enable_glue": bool_env("ENABLE_GLUE", False),
        },
        "properties_loaded": len(VERIFIED_PROPERTIES),
        "documents_registered": len(active_docs),
        "vector_chunks_indexed": len(vector_store.chunks_metadata),
    }


@app.get("/api/providers")
def get_providers():
    """Returns available AI provider status (Amazon Bedrock)."""
    bedrock = BedrockService()
    return {
        "status": "success",
        "active_provider": "bedrock",
        "providers": {
            "bedrock": {
                "name": "Amazon Bedrock",
                "available": bedrock.has_credentials(),
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
    """Lists indexed architectural documents and structured datasets from persistent DocumentRegistry."""
    registry = get_document_registry()
    docs = registry.list_all()
    
    # If registry is fresh, populate fallback from cached documents
    if not docs:
        s3_service = S3Service()
        cached = s3_service.get_cached_documents()
        docs = [
            {
                "filename": p.name,
                "file_type": p.suffix.lower().lstrip("."),
                "size_bytes": p.stat().st_size if p.exists() else 0,
                "status": "indexed",
            }
            for p in cached
        ]

    return {
        "status": "success",
        "count": len(docs),
        "documents": docs,
    }


@app.post("/api/documents/upload", dependencies=[Depends(require_admin_auth)])
async def upload_document(request: Request, filename: Optional[str] = None):
    """Administrative upload for documents to S3 and automated re-indexing."""
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

    try:
        sync_result = sync_all_pipeline()
    except IndexingConflictError as conflict_err:
        raise HTTPException(status_code=409, detail=str(conflict_err))
    except S3AccessError as s3_err:
        raise HTTPException(status_code=503, detail=f"S3 storage error: {s3_err}")

    registry = get_document_registry()
    doc_entry = registry.get(target_name)

    return {
        "status": "success",
        "message": "Document processed and synchronized successfully",
        "filename": target_name,
        "document": doc_entry,
        "sync_summary": sync_result,
    }


@app.post("/api/documents/reindex", dependencies=[Depends(require_admin_auth)])
def reindex_documents(force_rebuild: bool = False):
    """
    Manually triggers full document synchronization and allows full index rebuilds.
    Retries previously failed documents.
    """
    try:
        sync_result = sync_all_pipeline(force_rebuild=force_rebuild)
        return {
            "status": "success",
            "message": "Manual reindexing completed successfully",
            "force_rebuild": force_rebuild,
            "summary": sync_result,
        }
    except IndexingConflictError as conflict_err:
        raise HTTPException(status_code=409, detail=str(conflict_err))
    except S3AccessError as s3_err:
        raise HTTPException(status_code=503, detail=f"S3 access failure: {s3_err}")


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
    bhk_val: Optional[int] = None
    if filters.bhk is not None:
        try:
            bhk_val = int(filters.bhk)
        except (ValueError, TypeError):
            pass
    if bhk_val is None:
        bhk_str = extract_bhk_config(query)
        if bhk_str:
            m = re.search(r"(\d+)", bhk_str)
            if m:
                bhk_val = int(m.group(1))

    retrieved_chunks = retrieve_relevant_chunks(
        query=query,
        top_k=5,
        bhk=bhk_val,
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
