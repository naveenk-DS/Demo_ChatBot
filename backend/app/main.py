import logging
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
from .rag.image_assets import list_image_assets, ingest_image_assets, get_image_status_message, search_image_assets

logger = logging.getLogger(__name__)

app = FastAPI(title="Real Estate AI Demo API")
origins = [x.strip() for x in env("CORS_ORIGINS", "http://localhost:5173").split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True,
                   allow_methods=["GET", "POST"], allow_headers=["*"])

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
    return {"status": "ok"}


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
        history = [m.model_dump() for m in req.history]
        filters = understand(req.provider, history, req.message)
        if req.filters:
            explicit = req.filters.model_dump(exclude_unset=True, exclude_none=True)
            if explicit:
                merged = filters.model_dump()
                merged.update(explicit)
                filters = SearchFilters.model_validate(merged)

        # 1. Media requests (images, photos, walkthroughs, room visuals)
        if filters.intent == "media_request":
            search_res = search_image_assets(req.message)
            return {
                "status": "message",
                "assistant_message": search_res["assistant_message"],
                "filters": filters.model_dump(),
                "properties": [],
                "images": search_res["images"],
                "image_filter": {
                    "active": True,
                    "is_all": search_res["is_all"],
                    "category": search_res["display_name"],
                    "matched_count": search_res["matched_count"],
                    "total_available": search_res["total_available"],
                    "available_categories": search_res["available_categories"],
                },
            }

        # 2. Reset / Forget budget requests
        user_msg_lower = req.message.lower()
        if any(p in user_msg_lower for p in ["forget the budget", "forget budget", "ignore the budget", "ignore budget", "clear budget", "reset budget"]):
            filters.min_price = None
            filters.max_price = None
            return {
                "status": "message",
                "assistant_message": "Understood, I have cleared the budget filter. What property specifications or features would you like to explore?",
                "filters": filters.model_dump(),
                "properties": [],
            }

        # 3. Document QA (Specifications, dimensions, comparisons, room counts, entrance)
        if filters.intent == "document_qa":
            try:
                # Configuration hint: only pass if specifically one config is requested
                config_hint = None
                has_2bhk = "2bhk" in user_msg_lower or "2 bedroom" in user_msg_lower or "two bedroom" in user_msg_lower
                has_3bhk = "3bhk" in user_msg_lower or "three bedroom" in user_msg_lower or "3 bedroom" in user_msg_lower
                if has_2bhk and not has_3bhk:
                    config_hint = "2BHK"
                elif has_3bhk and not has_2bhk:
                    config_hint = "3BHK"
                elif filters.bhk == 2 and not has_3bhk:
                    config_hint = "2BHK"
                elif filters.bhk == 3 and not has_2bhk:
                    config_hint = "3BHK"

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
    except Exception as exc:
        logger.error("Chat request failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))

@app.post("/api/enquiries")
def enquiry(req: EnquiryRequest):
    if not req.consent:
        raise HTTPException(status_code=400, detail="Customer consent is required.")
    try:
        enquiry_id = save_enquiry(req.model_dump())
        return {"status": "success", "enquiry_id": enquiry_id, "message": "Enquiry submitted."}
    except Exception:
        raise HTTPException(status_code=500, detail="Unable to save enquiry.")
