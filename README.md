# EstateAI – AI-Powered Real Estate Concierge

EstateAI is an enterprise-grade AI concierge application for real estate property discovery, brochure document question answering (RAG), and customer enquiry capture.

The application is architected for deployment on **Amazon Web Services (AWS)** using:
- **Amazon Bedrock Knowledge Bases**: Managed document ingestion, embeddings, and semantic/hybrid retrieval over architectural project brochures via `bedrock-agent-runtime`.
- **Amazon Bedrock Nova**: State-of-the-art conversational generation and grounded answer synthesis via Bedrock Converse API (`amazon.nova-pro-v1:0` / `amazon.nova-lite-v1:0`).
- **Amazon S3 (`cg-website-chatbot-data`)**: Central storage for structured property datasets (CSV, Excel `.xlsx`, JSON) and unstructured PDF project brochures across project subfolders.
- **Amazon EC2**: High-performance FastAPI backend and React concierge frontend hosted on Ubuntu Linux with Nginx reverse proxy.
- **Local FAISS Fallback**: Preserved strictly for offline local development and testing without live AWS credentials.

---

## 1. System Architecture

```
                                 +-----------------------------------+
                                 |         React Frontend UI         |
                                 |     (EstateAI Concierge Widget)   |
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
|  +--------------------+          |  * /api/documents - S3 Catalog, Incremental Sync & Rebuild    |  |
|                                  |  * /api/enquiries - Customer Lead & Enquiry Management        |  |
|                                  |  * /api/assets/images - Property Media Serving                |  |
|                                  +---------------+-------------------------------+---------------+  |
|                                                  |                               |                  |
|                                                  v                               v                  |
|                                     +-------------------------+     +-------------------------+     |
|                                     | Deterministic Search    |     | Document Specification  |     |
|                                     | (CSV / XLSX / JSON)     |     | Retrieval Dispatcher    |     |
|                                     +------------+------------+     +------------+------------+     |
|                                                  |                               |                  |
|                                                  v                               |                  |
|                                     +-------------------------+                  |                  |
|                                     | In-Memory Store         |                  |                  |
|                                     | (Verified Properties)   |                  |                  |
|                                     +-------------------------+                  |                  |
+--------------------------------------------------+-------------------------------|------------------+
                                                   |                               |
                   ┌───────────────────────────────┘                               │
                   ▼                                                               ▼
     +---------------------------+                               +------------------------------------+
     |         Amazon S3         |                               |           Amazon Bedrock           |
     | (cg-website-chatbot-data) |                               |                                    |
     | - Structured Catalogs     |                               | * Knowledge Bases (Retrieve API)   |
     | - Project Subfolders      |                               |   - Hybrid / Semantic Retrieval    |
     | - Strictly Read-Only      |                               | * Nova Pro / Lite (Converse API)   |
     +---------------------------+                               +------------------------------------+
```

---

## 2. Document & Ingestion Architecture

### Data Separation Principle
The application cleanly separates structured inventory data from unstructured project documents:
- **Structured Datasets (`.csv`, `.xlsx`, `.xls`, `.json`):** Synchronized from the S3 bucket into memory (`StructuredDataStore`) for 100% deterministic property matching (BHK, price ceiling, location, facing, sq.ft.). The LLM is never permitted to invent property prices or availability.
- **Unstructured Documents (`.pdf`):** Ingested and indexed in AWS by the Team Lead into an Amazon Bedrock Knowledge Base. The backend queries the Knowledge Base via `bedrock-agent-runtime.retrieve()` to answer architectural and specification questions.

### Configurable Retrieval Modes
- **Search Type (`BEDROCK_KB_SEARCH_TYPE`):** Supports `HYBRID` (vector + text search) or `SEMANTIC` (pure vector search), aligning with the vector store backing the Knowledge Base (Amazon OpenSearch Serverless, Pinecone, or Amazon Aurora).
- **Production Guard (No Silent Fallback):** When `BEDROCK_KNOWLEDGE_BASE_ID` is configured, retrieval failures in production (`APP_ENV=production`) raise explicit exceptions and never silently fall back to stale local vectors.
- **Offline / Local Dev Fallback:** When `BEDROCK_KNOWLEDGE_BASE_ID` is unset, the application automatically engages local FAISS + BM25 hybrid search over cached documents.

---

## 3. Security & IAM Roles Separation

To follow AWS security best practices, the EC2 application role is completely separated from the Bedrock Knowledge Base service role:

1. **EC2 Application Role (`deploy/ec2_app_role_policy.json`):**
   - Attached to the EC2 instance profile.
   - `bedrock:InvokeModel` and `bedrock:InvokeModelWithResponseStream` on Amazon Nova and Claude models.
   - `bedrock:Retrieve` and `bedrock:RetrieveAndGenerate` on Bedrock Knowledge Bases.
   - **Strictly Read-Only on S3:** `s3:GetObject`, `s3:ListBucket`, `s3:GetBucketLocation` on `cg-website-chatbot-data`.
   - `s3:PutObject` and `s3:DeleteObject` are **completely omitted**.
2. **Bedrock Knowledge Base Service Role (`deploy/bedrock_kb_service_role_policy.json`):**
   - Assumed by `bedrock.amazonaws.com` for S3 ingestion and embedding generation.
   - Embeddings invocation (`bedrock:InvokeModel` on Titan Embeddings v2).
   - Read access to S3 bucket data source.
   - OpenSearch Serverless collection access (`aoss:APIAccessAll`).

---

## 4. Directory Layout

```
real_estate_ai_demo/
├── backend/
│   ├── app/
│   │   ├── data_pipeline/
│   │   │   └── structured.py          # CSV, XLSX, JSON deterministic parser
│   │   ├── rag/
│   │   │   ├── chunker.py             # Semantic document chunker (dev fallback)
│   │   │   ├── loader.py              # PyMuPDF extractor (dev fallback)
│   │   │   ├── retriever.py           # Unified dispatcher (Bedrock KB vs FAISS fallback)
│   │   │   └── store.py               # Local FAISS vector store (dev fallback)
│   │   ├── services/
│   │   │   ├── bedrock_kb_service.py  # Amazon Bedrock Knowledge Bases Retrieve API
│   │   │   ├── bedrock_service.py     # Amazon Bedrock Nova Converse API synthesis
│   │   │   ├── document_registry.py   # Persistent document tracking
│   │   │   ├── lock_service.py        # Process indexing lock
│   │   │   └── s3_service.py          # S3 dynamic discovery across project folders
│   │   ├── config.py                  # Unified environment loader
│   │   ├── enquiries.py               # Customer lead SQLite database store
│   │   ├── main.py                    # FastAPI application & chat orchestrator
│   │   └── schemas.py                 # Pydantic models & API contract definitions
│   ├── data/
│   │   ├── documents/                 # Local cache of property catalogs
│   │   └── faiss_index/               # Local persistent FAISS files (dev fallback)
│   ├── tests/                         # Full automated test suite (63 unit & integration tests)
│   ├── Dockerfile                     # Multi-stage production Dockerfile
│   └── requirements.txt               # Clean Python dependencies
├── deploy/
│   ├── ec2_app_role_policy.json       # EC2 IAM application role policy (Nova + KB + S3 Read-Only)
│   ├── bedrock_kb_service_role_policy.json # Bedrock Knowledge Base service role policy
│   ├── estateai.service               # Systemd service unit for Ubuntu EC2
│   ├── nginx.conf                     # Nginx reverse proxy configuration
│   └── setup_ec2.sh                   # Automated EC2 setup script
├── frontend/                          # React + Vite Concierge Chatbot UI
│   ├── src/
│   │   ├── components/                # ConciergeWidget, PropertyDetailCard, Carousel, Modal
│   │   ├── App.jsx                    # Root state & API integration
│   │   └── style.css                  # Custom styling (Teal / Forest-green theme)
│   ├── package.json
│   └── vite.config.js
├── .env.example                       # Root environment variable template
├── .gitignore                         # Comprehensive Git exclusion rules
└── README.md
```

---

## 5. Local Development Setup

### Backend Setup

1. **Create virtual environment and install dependencies:**
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure Environment:**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` as appropriate:
   ```ini
   APP_ENV=development
   AWS_REGION=ap-south-1
   S3_BUCKET_NAME=casa-chatbot
   S3_DOCUMENT_PREFIX=brochures/
   S3_STRUCTURED_DATA_PREFIX=Csv-data/
   S3_ALLOWED_PROJECT_PREFIXES=Casamia/,Zodiac/,Highlin/,Suncity/,Aquagroue/
   BEDROCK_NOVA_MODEL_ID=amazon.nova-pro-v1:0
   BEDROCK_KNOWLEDGE_BASE_ID=YOUR_BEDROCK_KNOWLEDGE_BASE_ID
   BEDROCK_KB_SEARCH_TYPE=HYBRID
   ALLOW_LOCAL_FALLBACK=true
   AWS_EC2_METADATA_DISABLED=true
   ADMIN_API_KEY=dev-secret-key-123
   ```
   *(Note: When AWS credentials or Knowledge Base ID are not configured locally, the backend automatically uses deterministic rule-based query handling and local cached documents).*

   **S3 Bucket & Folder Architecture (`casa-chatbot`):**
   ```text
   casa-chatbot/                       (S3 bucket)
   │
   ├── brochures/                      (Unstructured PDF brochures)
   │   ├── Casamia/
   │   ├── Zodiac/
   │   ├── Highlin/
   │   ├── Suncity/
   │   └── Aquagroue/
   │
   └── Csv-data/                       (Shared structured CSV/XLSX/JSON datasets)
       └── [chennai_premium_listings.csv, etc.]
   ```

3. **Run the backend:**
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

### Frontend Setup

1. **Install and run frontend:**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
2. The concierge chatbot will be accessible at `http://localhost:5173`.

---

## 6. Running the Test Suite

Run the full automated test suite (69 tests covering dynamic S3 discovery, project folder prefix filtering, multi-page pagination, Knowledge Base Retrieve API, HYBRID/SEMANTIC search types, production fail-closed protection, offline FAISS fallback, and chat endpoints):

```bash
cd backend
python -m unittest tests/test_structured_pipeline.py tests/test_pdf_rag.py tests/test_integration_and_fallbacks.py tests/test_chat_endpoints.py tests/test_dynamic_s3_and_lifecycle.py tests/test_bedrock_kb_retrieval.py tests/test_s3_project_filtering.py -v
```

---

## 7. API Endpoints Reference

| Method | Path | Auth | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | None | Health check, Bedrock Nova, Knowledge Base, and S3 status |
| `GET` | `/api/providers` | None | Active AI provider info (`{"active": "bedrock", "knowledge_base": {...}}`) |
| `POST` | `/api/chat` | None | Main conversational concierge endpoint (Nova + KB RAG) |
| `GET` | `/api/documents` | None | List indexed catalog files and brochures |
| `POST` | `/api/documents/upload` | Bearer | Administrative upload of documents to S3 with atomic collision check |
| `POST` | `/api/documents/reindex` | Bearer | Trigger document sync or staged full index rebuild (`?force_rebuild=true`) |
| `GET` | `/api/assets/images` | None | List available property image assets with category filter |
| `GET` | `/api/assets/images/{filename}` | None | Serve specific property images |
| `POST` | `/api/enquiries` | None | Save customer lead or contact enquiry |
