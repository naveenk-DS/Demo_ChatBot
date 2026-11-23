import logging
import re
from typing import Optional
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .config import env
from .schemas import ChatRequest, EnquiryRequest
from .llm import understand
from .sql_builder import build_sql
from .sql_validator import validate_generated_sql
from .athena import run_query
from .enquiries import save_enquiry
from .rag.service import answer_question
from .rag.store import sync_pdf_documents
from .rag.image_assets import list_image_assets, ingest_image_assets, get_image_status_message, search_image_assets

logger = logging.getLogger(__name__)

# Synchronize any newly added PDF documents into ChromaDB on startup
try:
    sync_pdf_documents()
except Exception as _sync_err:
    logger.debug("Initial PDF sync skipped: %s", _sync_err)


def extract_bhk_config(text: str, fallback_bhk: Optional[int] = None) -> Optional[str]:
    """Dynamically extracts target BHK unit configuration (e.g. 1BHK, 2BHK, 3BHK, 4BHK).
    Returns None if comparing multiple BHKs or if no specific BHK is mentioned."""
    lower = text.lower()
    matches = set(re.findall(r"\b([1-9])\s*bhk\b", lower))
    if len(matches) == 1:
        return f"{matches.pop()}BHK"
    if len(matches) > 1:
        # Comparing multiple BHKs
        return None

    word_to_num = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
    bedroom_matches = set()
    for word, num in word_to_num.items():
        if f"{word} bedroom" in lower or f"{num} bedroom" in lower:
            bedroom_matches.add(num)
    if len(bedroom_matches) == 1:
        return f"{bedroom_matches.pop()}BHK"
    if len(bedroom_matches) > 1:
        return None

    if fallback_bhk and 1 <= fallback_bhk <= 9:
        return f"{fallback_bhk}BHK"
    return None

app = FastAPI(title="Real Estate AI Demo API")

# Robust CORS Configuration: seamlessly supports local development, Render deployment, and custom origins
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
    for default_origin in ["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173", "http://127.0.0.1:3000"]:
        if default_origin not in explicit_origins:
            explicit_origins.append(default_origin)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=explicit_origins,
        allow_origin_regex=r"https://.*\.onrender\.com",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Mount local image assets directory for direct static serving
assets_dir = Path(__file__).resolve().parent.parent / "data" / "assets" / "images"
assets_dir.mkdir(parents=True, exist_ok=True)
app.mount("/api/assets/images", StaticFiles(directory=str(assets_dir)), name="assets_images")


def _get_image_assets_payload() -> list[dict]:
    """Helper to return formatted image assets metadata with accessible URLs."""
    assets = list_image_assets()
    if not assets:
        assets = ingest_image_assets()
    return [
        {
            "filename": a.get("filename"),
            "category": a.get("category", "general"),
            "property_name": a.get("property_name", "General Property"),
            "file_type": a.get("file_type", "image/jpeg"),
            "file_size_bytes": a.get("file_size_bytes", 0),
            "url": f"/api/assets/images/{a.get('filename')}",
        }
        for a in assets
    ]


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "real-estate-ai-demo",
        "environment": env("APP_ENV", "development"),
        "providers": {
            "gemini": bool(env("GEMINI_API_KEY") or env("GOOGLE_API_KEY")),
            "openai": bool(env("OPENAI_API_KEY")),
            "ollama": True,
        },
    }


@app.get("/api/providers")
def get_providers():
    """Returns available LLM provider status without exposing secrets."""
    gemini_model = env("GEMINI_MODEL", "gemini-3.5-flash-lite")
    return {
        "status": "success",
        "providers": {
            "ollama": {
                "id": "ollama",
                "name": "Ollama (Local Private AI)",
                "model": env("OLLAMA_CHAT_MODEL", env("OLLAMA_LLM_MODEL", env("LLM_MODEL", "qwen2.5:3b"))),
                "is_cloud": False,
            },
            "gemini": {
                "id": "gemini",
                "name": f"Google Gemini ({gemini_model})",
                "model": gemini_model,
                "configured": bool(env("GEMINI_API_KEY") or env("GOOGLE_API_KEY")),
                "is_cloud": True,
            },
            "openai": {
                "id": "openai",
                "name": "OpenAI (GPT-4.1-mini)",
                "model": env("OPENAI_MODEL", "gpt-4.1-mini"),
                "configured": bool(env("OPENAI_API_KEY")),
                "is_cloud": True,
            },
        },
    }


@app.get("/api/assets/images")
def get_images(category: Optional[str] = None):
    """Returns catalog of registered plain image assets, optionally filtered by category."""
    if category:
        search_res = search_image_assets(category)
        return {
            "status": "success",
            "images": search_res["images"],
            "total": search_res["matched_count"],
            "available_categories": search_res["available_categories"],
            "category": search_res["category"],
        }
    images = _get_image_assets_payload()
    return {
        "status": "success",
        "images": images,
        "total": len(images),
        "available_categories": sorted(list({img.get("category", "").title() for img in images if img.get("category")})),
    }

@app.post("/api/chat")
def chat(req: ChatRequest):
    try:
        user_msg_lower = req.message.lower().strip()

        # FAST-PATH 1: Media requests (images, photos, room visuals, or contextual references to rooms)
        visual_action = any(
            user_msg_lower.startswith(p) or f" {p} " in user_msg_lower or user_msg_lower.startswith(f"{p} ")
            for p in ["show me", "show", "display", "view", "see", "look at", "can you show", "can i see", "could you show"]
        )
        has_media_word = any(k in user_msg_lower for k in ["image", "images", "photo", "photos", "picture", "pictures", "virtual tour", "gallery"])
        has_room_term = any(t in user_msg_lower for t in ["master bedroom", "bedroom", "bathroom", "kitchen", "balcony", "living", "dining", "entrance", "floor plan"])
        has_contextual_room_ref = any(phrase in user_msg_lower for phrase in ["that room", "this room", "the room", "show it", "show that", "show me that", "see it", "view it", "display it"])
        has_doc_qa_keyword = any(k in user_msg_lower for k in ["dimension", "dimensions", "specification", "specifications", "size", "area", "sqft", "measure", "how many", "does the", "compare", "what are"])

        is_media = (has_media_word or (visual_action and (has_room_term or has_contextual_room_ref))) and not has_doc_qa_keyword
        if is_media:
            history_list = [m.model_dump() for m in req.history]
            search_res = search_image_assets(req.message, history=history_list)
            return {
                "status": "message",
                "assistant_message": search_res["assistant_message"],
                "filters": {"intent": "media_request"},
                "properties": [],
                "images": search_res.get("images", []),
                "image_filter": {
                    "active": True,
                    "is_all": search_res.get("is_all", False),
                    "category": search_res.get("display_name", "Images"),
                    "matched_count": search_res.get("matched_count", 0),
                    "total_available": search_res.get("total_available", 0),
                    "available_categories": search_res.get("available_categories", []),
                } if search_res.get("images") else None,
            }

        # FAST-PATH 2: Reset / Forget budget requests
        if any(p in user_msg_lower for p in ["forget the budget", "forget budget", "ignore the budget", "ignore budget", "clear budget", "reset budget"]):
            return {
                "status": "message",
                "assistant_message": "Understood, I have cleared the budget filter. What property specifications or features would you like to explore?",
                "filters": {"intent": "general_question", "min_price": None, "max_price": None},
                "properties": [],
            }

        # FAST-PATH 3: Unambiguous Document QA (specifications, dimensions, comparisons, room counts, entrance, document details)
        # Avoids making a redundant extra cloud LLM call just to classify intent!
        has_doc_qa_keyword = any(k in user_msg_lower for k in [
            "dimension", "dimensions", "specification", "specifications", "document detail", "document details",
            "entrance feature", "entrance features", "which is better", "compare 2bhk",
            "compare 3bhk", "compare", "all three bedrooms", "three bedrooms", "five bedrooms", "four bedrooms",
            "how many bedrooms", "does the 3bhk have", "does the 2bhk have", "does the 4bhk have",
            "script", "floor plan", "amenities", "amenity"
        ]) or (
            bool(re.search(r"\b[1-9]\s*bhk\b", user_msg_lower))
            and any(w in user_msg_lower for w in ["detail", "details", "info", "information", "script", "doc", "document", "spec", "about", "tell me about"])
        )
        has_search_criteria = any(k in user_msg_lower for k in [
            "lakh", "crore", "budget", "price", "under", "below", "above", "in chennai", "in bangalore",
            "in mumbai", "in delhi", "in hyderabad", "for sale", "buy", "rent"
        ])

        if has_doc_qa_keyword and not has_search_criteria:
            config_hint = extract_bhk_config(user_msg_lower)
            rag_res = answer_question(
                req.message,
                configuration=config_hint,
                provider=req.provider,
            )
            if rag_res.get("success") and rag_res.get("answer"):
                bhk_num = int(config_hint[0]) if config_hint and config_hint[0].isdigit() else None
                return {
                    "status": "message",
                    "assistant_message": rag_res.get("answer"),
                    "sources": rag_res.get("sources", []),
                    "filters": {
                        "intent": "document_qa",
                        "bhk": bhk_num,
                    },
                    "properties": [],
                }
            elif not rag_res.get("success") and rag_res.get("error"):
                err_msg = rag_res.get("error")
                if "timed out" in err_msg.lower() or "timeout" in err_msg.lower():
                    raise HTTPException(
                        status_code=504,
                        detail="The AI provider timed out while generating document specifications. Please try again."
                    )
                raise HTTPException(
                    status_code=502,
                    detail=f"AI provider failed: {err_msg}"
                )

        # Conversational understanding for multi-turn search & property inquiries
        history = [m.model_dump() for m in req.history]
        filters = understand(req.provider, history, req.message)
        if req.filters:
            explicit = req.filters.model_dump(exclude_unset=True, exclude_none=True)
            if explicit:
                merged = filters.model_dump()
                merged.update(explicit)
                filters = SearchFilters.model_validate(merged)

        # Media request handling from conversational understanding
        if filters.intent == "media_request":
            search_res = search_image_assets(req.message, history=history)
            return {
                "status": "message",
                "assistant_message": search_res["assistant_message"],
                "filters": filters.model_dump(),
                "properties": [],
                "images": search_res.get("images", []),
                "image_filter": {
                    "active": True,
                    "is_all": search_res.get("is_all", False),
                    "category": search_res.get("display_name", "Images"),
                    "matched_count": search_res.get("matched_count", 0),
                    "total_available": search_res.get("total_available", 0),
                    "available_categories": search_res.get("available_categories", []),
                } if search_res.get("images") else None,
            }

        # 3. Document QA (Specifications, dimensions, comparisons, room counts, entrance)
        if filters.intent == "document_qa":
            try:
                # Configuration hint: dynamically detect single BHK target
                config_hint = extract_bhk_config(user_msg_lower, fallback_bhk=filters.bhk)

                rag_res = answer_question(
                    req.message,
                    configuration=config_hint,
                    provider=req.provider,
                )
                if rag_res.get("success") and rag_res.get("answer"):
                    return {
                        "status": "message",
                        "assistant_message": rag_res.get("answer"),
                        "sources": rag_res.get("sources", []),
                        "filters": filters.model_dump(),
                        "properties": [],
                    }
            except Exception as rag_err:
                logger.warning("RAG document_qa failed: %s", rag_err)

        # 4. General question fallback with RAG check
        if filters.intent == "general_question":
            try:
                rag_res = answer_question(req.message, provider=req.provider)
                if rag_res.get("success") and rag_res.get("sources"):
                    ans = rag_res.get("answer")
                    if ans and not ans.startswith("I couldn't find this information in the available property documents."):
                        return {
                            "status": "message",
                            "assistant_message": ans,
                            "sources": rag_res.get("sources", []),
                            "filters": filters.model_dump(),
                            "properties": [],
                        }
            except Exception as rag_err:
                logger.warning("RAG answer lookup failed: %s", rag_err)

        # 5. Clarification required for property search
        if filters.needs_clarification:
            clarify_msg = filters.clarification_question or filters.assistant_message
            if not clarify_msg or "image of the land" in clarify_msg.lower():
                if filters.max_price:
                    clarify_msg = f"I've noted your budget of around ₹{filters.max_price // 100000} Lakhs. Which city or locality are you looking for?"
                else:
                    clarify_msg = "Which city or locality and budget do you have in mind for your property search?"
            return {
                "status": "clarification_required",
                "assistant_message": clarify_msg,
                "filters": filters.model_dump(),
                "properties": [],
            }

        # 6. Contact request
        if filters.intent == "contact_request":
            return {
                "status": "message",
                "assistant_message": filters.assistant_message or "You can schedule a site visit or submit an inquiry using the enquiry form.",
                "filters": filters.model_dump(),
                "properties": [],
            }

        # 7. Non-search fallback
        if filters.intent != "property_search":
            return {
                "status": "message",
                "assistant_message": filters.assistant_message or "I can help search properties or answer brochure specifications. How can I help?",
                "filters": filters.model_dump(),
                "properties": [],
            }

        # 8. Property Search (SQL + Athena)
        sql = build_sql(filters)
        validate_generated_sql(sql)
        try:
            records = run_query(sql)
        except Exception as q_err:
            logger.warning("Property query failed: %s", q_err)
            records = []
        return {
            "status": "success",
            "assistant_message": filters.assistant_message or f"Found {len(records)} matching property record(s).",
            "filters": filters.model_dump(),
            "properties": records,
            "result_count": len(records),
            "images": [],
            "image_filter": None,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Chat request failed: %s", exc)
        err_msg = str(exc)
        if "timed out" in err_msg.lower() or "timeout" in err_msg.lower():
            raise HTTPException(
                status_code=504,
                detail="The AI provider took too long to respond. Please try again.",
            )
        raise HTTPException(status_code=500, detail=err_msg)

@app.post("/api/enquiries")
def enquiry(req: EnquiryRequest):
    if not req.consent:
        raise HTTPException(status_code=400, detail="Customer consent is required.")
    try:
        enquiry_id = save_enquiry(req.model_dump())
        return {"status": "success", "enquiry_id": enquiry_id, "message": "Enquiry submitted."}
    except Exception:
        raise HTTPException(status_code=500, detail="Unable to save enquiry.")
