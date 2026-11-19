from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .config import env
from .schemas import ChatRequest, EnquiryRequest
from .llm import understand
from .sql_builder import build_sql
from .sql_validator import validate_generated_sql
from .athena import run_query
from .enquiries import save_enquiry

app = FastAPI(title="Real Estate AI Demo API")
origins = [x.strip() for x in env("CORS_ORIGINS", "http://localhost:5173").split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True,
                   allow_methods=["GET", "POST"], allow_headers=["*"])

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/api/chat")
def chat(req: ChatRequest):
    try:
        history = [m.model_dump() for m in req.history]
        filters = understand(req.provider, history, req.message)
        if filters.needs_clarification:
            return {"status": "clarification_required",
                    "assistant_message": filters.clarification_question or filters.assistant_message,
                    "filters": filters.model_dump(), "properties": []}
        if filters.intent != "property_search":
            return {"status": "message",
                    "assistant_message": filters.assistant_message or "I can help search properties. What location and budget do you have in mind?",
                    "filters": filters.model_dump(), "properties": []}
        sql = build_sql(filters)
        validate_generated_sql(sql)
        records = run_query(sql)
        return {"status": "success",
                "assistant_message": filters.assistant_message or f"Found {len(records)} matching property record(s).",
                "filters": filters.model_dump(), "properties": records, "result_count": len(records)}
    except Exception as exc:
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
