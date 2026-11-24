# EstateAI – Comprehensive Backend & Architecture Audit

**Date:** 2026-11-24  
**Project:** EstateAI – Real Estate Conversational Concierge  
**Author:** Senior Backend & AWS Solutions Architect  

---

## 1. Executive Summary

EstateAI is an intelligent real estate concierge application consisting of a React + Vite frontend and a FastAPI backend. The application currently supports natural language property search, document question answering (RAG) over architectural/engineering PDF specifications, image asset retrieval, and site visit / brochure enquiries.

This audit evaluates the codebase ahead of refactoring the architecture to a clean, production-ready AWS deployment utilizing:
- **Amazon Bedrock** (chat orchestration, intent understanding, filter extraction, Titan v2 embeddings)
- **Amazon S3** (storage for structured datasets [CSV, Excel, JSON] and unstructured PDFs)
- **Amazon EC2** (FastAPI backend + persistent FAISS vector storage + React frontend)

---

## 2. File-by-File Backend Inventory

| File Path | LOC | Purpose | Dependencies / Key Imports | Audit Verdict |
| :--- | :---: | :--- | :--- | :--- |
| `backend/app/main.py` | 983 | Main FastAPI application, routing, CORS, chat orchestration, fallback catalogs, asset mounts. | FastAPI, schemas, llm, athena, sql_builder, rag, enquiries | **Refactor:** Decouple Athena fallback & hardcoded demo catalog; route chat through new Bedrock service and S3 structured data pipeline. |
| `backend/app/config.py` | 37 | Environment variable loading helper (`env`, `int_env`). | `os`, `pathlib.Path`, `dotenv` | **Keep & Enhance:** Add validation for Bedrock models, S3 bucket/prefixes, FAISS paths, and feature flags (`ENABLE_ATHENA`, `ENABLE_GLUE`). |
| `backend/app/schemas.py` | 89 | Pydantic data models for Chat, SearchFilters, Enquiry. | `pydantic`, `typing` | **Keep & Update:** Update `ChatRequest` provider literal to support `bedrock`; maintain strict filter validation. |
| `backend/app/llm.py` | 420 | Multi-provider LLM connector (OpenAI, Gemini, Ollama) for question understanding and filter extraction. | `openai`, `google.genai`, `urllib` (Ollama), `schemas` | **Replace/Refactor:** Remove active Gemini, OpenAI, and Ollama code. Replace with `BedrockService` using `boto3` and Bedrock Converse API / Titan Embeddings. |
| `backend/app/athena.py` | 41 | AWS Athena client and query polling. | `boto3`, `time`, `config` | **Retain (Disabled):** Keep source code intact; guard with `ENABLE_ATHENA=false` to ensure zero execution during chat. |
| `backend/app/sql_builder.py` | 37 | Sanitized SQL generator for Athena table queries. | `re`, `config`, `schemas` | **Retain (Disabled):** Keep intact for future Athena/Glue use. |
| `backend/app/sql_validator.py` | 14 | AST SQL validator using `sqlglot`. | `sqlglot`, `config` | **Retain (Disabled):** Keep intact. |
| `backend/app/enquiries.py` | 15 | SQLite customer enquiry persistence. | `sqlite3`, `config` | **Keep:** Maintain existing SQLite storage for customer enquiries (`enquiries.db`). |
| `backend/app/rag/__init__.py` | 41 | Convenience exports for RAG modules. | `loader`, `chunker`, `store`, `retriever` | **Update:** Export FAISS and Bedrock embedding components instead of ChromaDB and Ollama. |
| `backend/app/rag/loader.py` | 279 | PDF and CSV document loading using PyMuPDF (`fitz`) and Python CSV reader. | `fitz` (PyMuPDF), `csv`, `pathlib` | **Refactor:** Retain PyMuPDF text & page metadata extraction for PDFs. Delegate structured CSV/Excel/JSON parsing to dedicated S3 structured pipeline. |
| `backend/app/rag/chunker.py` | 293 | Token-aware text chunking with category and specification detection. | `re`, `pathlib`, `logging` | **Keep & Tune:** Well-structured chunker with sentence and boundary awareness (~800 token chunk size, ~120 overlap). |
| `backend/app/rag/store.py` | 319 | ChromaDB vector store client with Ollama embedding generation. | `chromadb`, `urllib` (Ollama) | **Replace:** Remove ChromaDB and Ollama. Implement lightweight, persistent FAISS index on EC2 with Amazon Titan Embeddings v2 (`amazon.titan-embed-text-v2:0`, 1024 dims). |
| `backend/app/rag/retriever.py` | 608 | Hybrid search combining BM25 and ChromaDB dense embeddings. | `chromadb`, `collections.Counter`, `math` | **Refactor:** Preserve BM25 keyword search; replace ChromaDB dense retrieval with FAISS vector search. |
| `backend/app/rag/service.py` | 328 | RAG synthesis generating answers via Ollama, OpenAI, or Gemini. | `urllib` (Ollama), `google.genai`, `openai` | **Refactor:** Direct grounded answer generation through Amazon Bedrock (`bedrock-runtime`). |
| `backend/app/rag/image_assets.py` | 551 | Image registry, categorization, and local file management. | `json`, `pathlib`, `shutil` | **Keep:** Stable image management for visual specification tiles and property photos. |

---

## 3. Frontend Integration Audit

| Frontend Component | API Endpoints Invoked | Payload / Data Flow | Compatibility Requirements |
| :--- | :--- | :--- | :--- |
| `frontend/src/App.jsx` | `POST /api/chat`<br>`POST /api/enquiries` | Sends `{ message, history, provider }`. Receives `{ assistant_message, properties, images, sources, filters }`. | Must preserve JSON schema and field names (`assistant_message`, `properties`, `images`, `sources`). |
| `frontend/src/components/ConciergeWidget.jsx` | Receives data from `App.jsx` | Renders conversation, typing indicators, suggested questions, provider selector. | Remove obsolete OpenAI/Ollama options from selector or set to Amazon Bedrock. |
| `frontend/src/components/PropertyDetailCard.jsx` | Static `/api/assets/images/{filename}` | Renders property details, dimensions, room tiles, images. | Image asset URLs must remain intact. |
| `frontend/src/components/EnquiryModal.jsx` | `POST /api/enquiries` | Sends `{ name, phone, property_id, message, consent }`. | Schema is validated by Pydantic `EnquiryRequest`. |

---

## 4. Dependencies & Package Audit

Current `backend/requirements.txt`:
```txt
fastapi
uvicorn[standard]
boto3
python-dotenv
pydantic
openai
google-genai
sqlglot
chromadb
```

### Analysis:
- **Obsolete / Removable:**
  - `openai` — Not used in Bedrock deployment.
  - `google-genai` — Not used in Bedrock deployment.
  - `chromadb` — Heavy C++ dependency with SQLite locking quirks; replaced with `faiss-cpu`.
- **Required New Dependencies:**
  - `pandas` — Structured data manipulation (CSV, Excel).
  - `openpyxl` — Excel (`.xlsx`) parsing.
  - `faiss-cpu` — Fast, lightweight vector similarity search on EC2.
  - `pymupdf` (fitz) — PDF text extraction (already in venv, must be pinned in `requirements.txt`).
- **Retained Dependencies:**
  - `fastapi`, `uvicorn[standard]` — Core web framework and ASGI server.
  - `boto3` — AWS SDK for S3, Bedrock Runtime, STS.
  - `python-dotenv` — Environment configuration.
  - `pydantic` — Data validation and schema enforcement.
  - `sqlglot` — Retained for Athena SQL validation.

---

## 5. Architectural Findings & Key Observations

1. **Hardcoded Fallbacks in `main.py`:**
   `main.py` currently holds a large `DEMO_PROPERTY_CATALOG` dictionary that serves as a fallback when Athena is unavailable. The new architecture must replace this with a deterministic, verified **S3 Structured Data Pipeline** (CSV, XLSX, JSON) that acts as the single source of truth.
2. **Athena & Glue Decoupling:**
   Athena queries in `_fetch_properties_for_bhk` currently cause timeouts or errors when Athena credentials or workgroups are absent. Per Phase 2, Athena and Glue code will be preserved in the repo, but gated behind `ENABLE_ATHENA=false` and `ENABLE_GLUE=false`.
3. **ChromaDB & Ollama Removal:**
   `store.py` and `service.py` currently invoke local Ollama endpoints (`http://localhost:11434/api/embeddings`) and store embeddings in a 1.3MB ChromaDB database. When Ollama is offline, embeddings fail or return errors. Replacing this with **Amazon Bedrock Titan v2** (`amazon.titan-embed-text-v2:0`) and **FAISS** ensures deterministic, cloud-native vector search on EC2 without running local LLM daemons.
4. **AWS Authentication:**
   Boto3 was previously attempting to read `AWS_PROFILE=realestate-demo` from `.env`, failing when the profile was absent. The refactored client will support:
   - EC2 IAM Instance Role (automatic credentials in production)
   - Standard AWS environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`)
   - Graceful fallback when running offline or testing.

