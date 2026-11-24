# EstateAI – AI-Powered Real Estate Concierge

EstateAI is an enterprise-grade AI concierge application for real estate property discovery, brochure document question answering (RAG), and customer enquiry capture.

The application has been refactored and architected for deployment on **Amazon Web Services (AWS)** using:
- **Amazon Bedrock**: LLM conversational synthesis (Anthropic Claude 3.5 Sonnet) & Titan Text Embeddings v2 (`amazon.titan-embed-text-v2:0`).
- **Amazon S3**: Central storage for structured property datasets (CSV, Excel `.xlsx`, JSON) and unstructured PDF project brochures.
- **Amazon EC2**: High-performance FastAPI backend with local persistent FAISS vector storage, served alongside a React concierge frontend via Nginx.

---

## 1. System Architecture

```
                                 +-----------------------------------+
                                 |         React Frontend UI         |
                                 |     (EstateAI Concierge Widget)    |
                                 +-----------------+-----------------+
                                                   | HTTP / REST
                                                   v
+--------------------------------------------------+--------------------------------------------------+
| Amazon EC2 Instance                                                                                 |
|                                                                                                     |
|  +--------------------+          +---------------------------------------------------------------+  |
|  |       Nginx        | -------> | FastAPI Backend (Uvicorn)                                     |  |
|  |  (Reverse Proxy /  |          |                                                               |  |
|  |   Static Host)     |          |  * /api/chat - Orchestrator & Natural Language Dispatcher     |  |
|  +--------------------+          |  * /api/documents - S3 Document Catalog & Sync Pipeline        |  |
|                                  |  * /api/enquiries - Customer Lead & Enquiry Management        |  |
|                                  |  * /api/assets/images - Property Media Serving                |  |
|                                  +---------------+-------------------------------+---------------+  |
|                                                  |                               |                  |
|                                                  v                               v                  |
|                                     +-------------------------+     +-------------------------+     |
|                                     | Deterministic Search    |     | Hybrid Document RAG     |     |
|                                     | (CSV / XLSX / JSON)     |     | (FAISS + BM25 + RRF)    |     |
|                                     +------------+------------+     +------------+------------+     |
|                                                  |                               |                  |
|                                                  v                               v                  |
|                                     +-------------------------+     +-------------------------+     |
|                                     | In-Memory Cache         |     | Persistent FAISS Index  |     |
|                                     | (Verified Properties)   |     | (/data/faiss_index/)    |     |
|                                     +-------------------------+     +-------------------------+     |
+--------------------------------------------------+-------------------------------+------------------+
                                                   |                               |
                                                   v                               v
                                     +-------------------------+     +-------------------------+
                                     |        Amazon S3        |     |     Amazon Bedrock      |
                                     |  (Catalog & Brochures)  |     | (Claude 3.5 & Titan v2) |
                                     +-------------------------+     +-------------------------+
```

---

## 2. Key Features

- **Accurate Property Search:** No LLM hallucination of prices or availability. Natural language queries are extracted into structured filters (BHK, price ceiling, location, facing, etc.) and queried against verified catalog files.
- **Dynamic & Expandable S3 Ingestion:** Ingests any number of supported documents (CSV, multi-sheet Excel `.xlsx`, nested JSON, and PDF) without code modifications. Features automatic S3 `list_objects_v2` pagination, fingerprint change detection (SHA-256), and safe ignoring of unsupported formats.
- **Full Document Lifecycle & Stale Data Purge:** When documents are modified or replaced in S3, stale structured records and vector chunks are automatically purged before re-indexing. When files are deleted from S3, searchable records are safely removed.
- **Persistent Document Registry:** Tracks S3 key, filename, file type, SHA-256 fingerprint, last modified timestamp, indexing status (`pending`, `processing`, `indexed`, `failed`), and chunk/record counts across EC2 restarts.
- **Hybrid RAG for Brochures:** Documents are indexed using PyMuPDF and embedded with Amazon Titan Embeddings v2 into a FAISS index, combined with BM25 keyword scoring via Reciprocal Rank Fusion (RRF).
- **Enterprise Security:**
  - Zero hardcoded credentials; uses AWS EC2 IAM Instance Profiles.
  - Path traversal defense on image and document downloads.
  - CORS security with configurable origin allowlists.
  - Retains Athena/Glue code for enterprise data lake queries, disabled by default via config flags.
- **Multi-Intent Dispatching:** Automatically distinguishes greetings, property search, document Q&A, photo/media requests, and enquiry capture in a unified conversation flow.

---

## 3. Directory Layout

```
real_estate_ai_demo/
├── backend/
│   ├── app/
│   │   ├── data_pipeline/
│   │   │   ├── __init__.py
│   │   │   └── structured.py          # CSV, XLSX, JSON parsing & deterministic search
│   │   ├── rag/
│   │   │   ├── chunker.py             # Semantic document chunking
│   │   │   ├── loader.py              # PyMuPDF PDF extraction & fingerprinting
│   │   │   ├── retriever.py           # Hybrid BM25 + FAISS vector retriever (RRF)
│   │   │   ├── service.py             # Grounded Bedrock Q&A generation
│   │   │   └── store.py               # FAISS vector store with NumPy fallback
│   │   ├── services/
│   │   │   ├── bedrock_service.py     # Amazon Bedrock Converse & Titan v2 embeddings
│   │   │   └── s3_service.py          # Amazon S3 download, sync & local caching
│   │   ├── athena.py                  # Athena query runner (disabled by default)
│   │   ├── config.py                  # Unified configuration & environment loaders
│   │   ├── enquiries.py               # Customer enquiry SQLite database store
│   │   ├── main.py                    # FastAPI application & chat orchestrator
│   │   └── schemas.py                 # Pydantic models & API contract definitions
│   ├── data/
│   │   ├── documents/                 # Local cache of structured property catalogs
│   │   └── faiss_index/               # Local persistent FAISS vector index files
│   ├── static/                        # Property images and assets
│   ├── tests/                         # Full automated test suite (24 unit & integration tests)
│   ├── Dockerfile                     # Multi-stage production Dockerfile
│   └── requirements.txt               # Clean Python dependencies
├── deploy/
│   ├── ec2_bedrock_s3_policy.json     # AWS IAM Policy for EC2 instance profile
│   ├── estateai.service               # Systemd service unit for Ubuntu EC2
│   ├── nginx.conf                     # Nginx reverse proxy configuration
│   └── setup_ec2.sh                   # Automated EC2 setup script
├── frontend/                          # React + Vite Concierge Chatbot UI
├── docker-compose.yml                 # Local & staging Docker Compose configuration
├── EC2_DEPLOYMENT_GUIDE.md            # Comprehensive AWS EC2 deployment walkthrough
├── BACKEND_AUDIT.md                   # Pre-refactor AST audit & technical debt log
├── EXISTING_API_CONTRACTS.md          # Complete API contract specification
├── REMOVAL_AND_REFACTOR_PLAN.md       # Architecture transition blueprint
└── IMPLEMENTATION_PROGRESS.md         # 12-phase progress & test report
```

---

## 4. Local Development Setup

### Backend Setup

1. **Navigate to backend and create virtual environment:**
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment:**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` as appropriate:
   ```ini
   AWS_REGION=us-east-1
   BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
   BEDROCK_EMBEDDING_MODEL_ID=amazon.titan-embed-text-v2:0
   S3_BUCKET_NAME=
   ENABLE_ATHENA=false
   ENABLE_GLUE=false
   ```
   *(Note: If AWS credentials are not configured locally, the backend gracefully falls back to deterministic rule-based query handling and NumPy vector similarity for testing).*

4. **Run the backend:**
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

### Frontend Setup

1. **Navigate to frontend:**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
2. The concierge chatbot will be accessible at `http://localhost:5173`.

---

## 5. Running the Test Suite

Run the full automated test suite (36 tests covering dynamic S3 discovery, pagination, incremental sync, stale data purges, multi-sheet Excel, PDF extraction, hybrid RAG, Bedrock fallback, and chat endpoints):

```bash
python -m unittest backend/tests/test_structured_pipeline.py backend/tests/test_pdf_rag.py backend/tests/test_integration_and_fallbacks.py backend/tests/test_chat_endpoints.py backend/tests/test_dynamic_s3_and_lifecycle.py -v
```

---

## 6. AWS EC2 Deployment

For production deployment instructions, see the comprehensive [EC2 Deployment Guide](EC2_DEPLOYMENT_GUIDE.md).

Quick summary:
1. Launch an EC2 instance (Ubuntu 22.04 LTS) and attach the IAM Role defined in `deploy/ec2_bedrock_s3_policy.json`.
2. Run `deploy/setup_ec2.sh` to install system packages, Python 3.11, Nginx, and Node.js.
3. Build the frontend with `npm run build`.
4. Enable the `estateai.service` systemd service and restart Nginx.

---

## 7. API Endpoints Reference

| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Health check & connection status (Bedrock, S3, catalog count) |
| `GET` | `/api/providers` | Active AI provider info (`{"active": "bedrock", ...}`) |
| `POST` | `/api/chat` | Main conversational concierge endpoint |
| `GET` | `/api/documents` | List uploaded PDF brochures and catalog files |
| `POST` | `/api/documents/upload` | Upload new PDF brochures or datasets to S3 |
| `GET` | `/api/assets/images` | List available property image assets |
| `GET` | `/api/assets/images/{filename}` | Serve specific property images |
| `POST` | `/api/enquiries` | Save customer lead or contact enquiry |

