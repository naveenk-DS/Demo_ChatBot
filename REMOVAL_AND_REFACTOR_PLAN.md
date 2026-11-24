# EstateAI – Removal & Refactoring Plan

**Target Stack:** Amazon Bedrock + Amazon S3 + Amazon EC2  
**Date:** 2026-11-24  

---

## 1. Inventory of Changes

### 1.1. Code & Dependencies to Remove
| Component / Package | Current Location | Reason for Removal | Safety Rationale |
| :--- | :--- | :--- | :--- |
| `openai` package | `backend/requirements.txt`, `llm.py`, `service.py` | Migrating to Bedrock-only architecture. | Bedrock Converse API replaces OpenAI chat completions. |
| `google-genai` package | `backend/requirements.txt`, `llm.py`, `service.py` | Migrating to Bedrock-only architecture. | Bedrock Converse API replaces Gemini calls. |
| Ollama HTTP calls | `llm.py`, `store.py`, `service.py` | Local Ollama daemon is fragile and unsuited for production EC2. | Bedrock Titan Embeddings v2 (`amazon.titan-embed-text-v2:0`) and Bedrock chat replace Ollama. |
| `chromadb` package | `backend/requirements.txt`, `store.py`, `retriever.py` | Heavy native dependency, SQLite lock issues, high memory footprint. | Replaced with `faiss-cpu`, a lightweight, blazing-fast, persistent vector index on EC2. |
| `DEMO_PROPERTY_CATALOG` fallback | `backend/app/main.py` | Hardcoded mock dictionary violating rule: "Never use hardcoded demo properties in production". | Replaced by deterministic **S3 Structured Data Pipeline** reading verified CSV, XLSX, and JSON files. |
| Frontend provider dropdown options | `frontend/src/components/ConciergeWidget.jsx` | Shows Gemini/OpenAI/Ollama options which are obsolete. | Set to clean Bedrock indicator or discreetly lock to Amazon Bedrock. |

---

### 1.2. Code to Retain (Disabled in Active Chat)
| Component | Location | Role & Configuration |
| :--- | :--- | :--- |
| `athena.py` | `backend/app/athena.py` | Retained for future AWS Athena queries; disabled via `ENABLE_ATHENA=false`. |
| `sql_builder.py` | `backend/app/sql_builder.py` | Retained for Athena SQL generation; disabled via `ENABLE_ATHENA=false`. |
| `sql_validator.py` | `backend/app/sql_validator.py` | Retained for SQL AST safety verification using `sqlglot`. |
| `enquiries.py` | `backend/app/enquiries.py` | Active: saves customer leads in SQLite `enquiries.db`. |
| `image_assets.py` | `backend/app/rag/image_assets.py` | Active: catalogs and serves property images for visual cards and specification tiles. |

---

### 1.3. New Architecture Modules
```
backend/app/
├── services/
│   ├── __init__.py
│   ├── bedrock_service.py     <-- Amazon Bedrock (Converse API + Titan Embeddings v2)
│   └── s3_service.py          <-- S3 bucket synchronization & document fetching
├── data_pipeline/
│   ├── __init__.py
│   ├── structured.py          <-- CSV, Excel (XLSX), JSON parsing, normalization & deterministic search
│   └── validator.py           <-- Pydantic record validation & price normalization
├── rag/
│   ├── chunker.py             <-- Preserved & tuned sentence/token chunker
│   ├── loader.py              <-- PyMuPDF PDF extraction & metadata preservation
│   ├── store.py               <-- FAISS index management on persistent EC2 storage
│   ├── retriever.py           <-- Hybrid search (BM25 keyword + FAISS Titan dense embeddings)
│   └── image_assets.py        <-- Local image catalog and URL resolution
├── main.py                    <-- Clean dispatcher orchestrating S3 search + RAG + Bedrock
└── config.py                  <-- Validated environment configuration with fallback handling
```

---

## 2. Refactoring Phase Breakdown

### Phase 3: Structured Document Processing Pipeline
1. Install `pandas` and `openpyxl`.
2. Implement `backend/app/data_pipeline/structured.py`:
   - `load_csv(file_path_or_bytes)` using Pandas.
   - `load_excel(file_path_or_bytes)` using Pandas + openpyxl (handling multi-sheet workbooks).
   - `load_json(file_path_or_bytes)` handling flat and nested structures.
   - `normalize_records(records, source_name)` mapping flexible column aliases (e.g. `price`, `cost`, `rate`, `bhk`, `bedrooms`, `location`, `area`, `sqft`) into standard schema.
   - `validate_records(records)` removing corrupt or empty entries.
   - `search_properties(query_filters, records)` providing deterministic, multi-criteria filtering (BHK, price bounds, location substring match, property type).
3. Connect with `s3_service.py` to pull structured documents from S3 bucket on startup and cache locally.

### Phase 4: Unstructured PDF Vector Indexing with Amazon Bedrock & FAISS
1. Install `faiss-cpu`.
2. Update `backend/app/rag/store.py`:
   - Replace ChromaDB with `FAISS` index (`IndexFlatIP` or `IndexFlatL2` normalized for cosine similarity).
   - Generate embeddings using Amazon Bedrock Titan Text Embeddings v2 (`amazon.titan-embed-text-v2:0`, 1024 dimensions).
   - Persist FAISS index file and chunk metadata JSON to EC2 disk (`VECTOR_STORE_PATH`).
   - Implement document fingerprinting (MD5/SHA256) to prevent redundant re-indexing on every chat or startup.
3. Update `backend/app/rag/retriever.py`:
   - Keep dynamic BM25 keyword search.
   - Combine BM25 scores with FAISS Titan vector scores using Reciprocal Rank Fusion (RRF) or normalized linear combination.

### Phase 5: Amazon Bedrock Service Integration
1. Implement `backend/app/services/bedrock_service.py`:
   - Use `boto3.client('bedrock-runtime', region_name=...)`.
   - Prefer Bedrock **Converse API** (`converse` / `converse_stream`) for chat models (e.g. `anthropic.claude-3-sonnet-20240229-v1:0` or `anthropic.claude-3-haiku-20240307-v1:0` or `amazon.nova-lite-v1:0`).
   - Implement structured filter extraction returning validated Pydantic `SearchFilters`.
   - Implement grounded Q&A generation taking retrieved PDF chunks and structured property records.
   - Implement exponential backoff retry for throttling (`ThrottlingException`) and timeouts.
   - Track token usage metrics.

### Phase 6: Chat Orchestrator Refactoring
1. Update `backend/app/main.py`:
   - Remove legacy fallback catalog `DEMO_PROPERTY_CATALOG`.
   - Dispatch user query:
     - If greeting -> Return conversational greeting immediately.
     - If media request -> Return image assets matching room category.
     - If property search / combined -> Query structured property dataset via `search_properties()`.
     - If document question / combined -> Retrieve relevant PDF chunks via `retrieve_relevant_chunks()`.
     - Synthesize response with Amazon Bedrock.
   - Format response matching exact existing API contract.

### Phase 7 & 8: Removal of Obsolete Code & API Compatibility
1. Remove `openai`, `google-genai`, `chromadb` from requirements.
2. Clean `main.py`, `schemas.py`, and `config.py`.
3. Update `frontend/src/components/ConciergeWidget.jsx` to reflect Amazon Bedrock.
4. Verify all routes: `/health`, `/api/providers`, `/api/chat`, `/api/documents`, `/api/assets/images`, `/api/enquiries`.

### Phase 9 & 10: Security, Testing & Verification
1. Validate input sanitization, upload size limits, path traversal defense.
2. Build comprehensive automated test suite:
   - Structured parsing tests (CSV, XLSX, multi-sheet, JSON, nested).
   - PDF chunking, metadata & FAISS indexing tests.
   - Bedrock service & fallback tests.
   - End-to-end chat flow tests.
   - Integration tests with Athena & Glue disabled.

### Phase 11 & 12: EC2 & GitHub Preparation
1. Create production `Dockerfile`, `docker-compose.yml` (optional).
2. Create complete `.env.example`, `.gitignore`.
3. Write EC2 IAM role documentation, Nginx reverse proxy & systemd service unit configurations.
4. Provide step-by-step Git commands for the office repository.

