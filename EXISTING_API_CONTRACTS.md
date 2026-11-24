# EstateAI – Existing API Contracts & Schemas

**Date:** 2026-11-24  
**Target:** API Compatibility Preservation for AWS Migration  

---

## 1. Overview

The EstateAI frontend relies on a specific set of REST API endpoints exposed by the FastAPI backend. To ensure zero disruption to the user interface, property cards, image carousels, or enquiry workflows, all API contracts are formally documented below and will be maintained during the AWS Bedrock + S3 + EC2 refactoring.

---

## 2. API Routes Specification

### 2.1. Health Check
- **Route:** `GET /health`
- **Purpose:** System readiness, environment status, and provider check.
- **Request:** None
- **Response `200 OK`:**
```json
{
  "status": "ok",
  "service": "estateai-concierge-backend",
  "environment": "production",
  "aws": {
    "region": "ap-south-1",
    "bedrock_chat_model": "anthropic.claude-3-sonnet-20240229-v1:0",
    "bedrock_embedding_model": "amazon.titan-embed-text-v2:0",
    "s3_bucket": "my-estate-bucket"
  },
  "flags": {
    "enable_athena": false,
    "enable_glue": false
  }
}
```

---

### 2.2. Provider Status
- **Route:** `GET /api/providers`
- **Purpose:** Inform frontend which AI providers are active without revealing credentials.
- **Request:** None
- **Response `200 OK`:**
```json
{
  "status": "success",
  "active_provider": "bedrock",
  "providers": {
    "bedrock": {
      "name": "Amazon Bedrock",
      "available": true,
      "chat_model": "anthropic.claude-3-sonnet-20240229-v1:0",
      "embedding_model": "amazon.titan-embed-text-v2:0"
    }
  }
}
```

---

### 2.3. Conversational Chat Dispatcher
- **Route:** `POST /api/chat`
- **Purpose:** Primary chat orchestration endpoint handling user queries, property search, document Q&A, and combined workflows.
- **Request Headers:** `Content-Type: application/json`
- **Request Body (`ChatRequest`):**
```json
{
  "message": "Show me 2BHK properties under 1.5 Cr in Chennai",
  "history": [
    {
      "role": "user",
      "content": "Hi there"
    },
    {
      "role": "assistant",
      "content": "Hello! How can I assist with your property search today?"
    }
  ],
  "provider": "bedrock",
  "filters": null
}
```
- **Response `200 OK`:**
```json
{
  "status": "success",
  "assistant_message": "I found 2 verified 2BHK properties matching your criteria in Chennai.",
  "filters": {
    "intent": "property_search",
    "location": "Chennai",
    "city": "Chennai",
    "bhk": 2,
    "min_price": null,
    "max_price": 15000000,
    "property_type": "Apartment",
    "needs_clarification": false,
    "clarification_question": null,
    "assistant_message": ""
  },
  "properties": [
    {
      "property_id": "PROP-2BHK-01",
      "property_name": "Casagrand Aquagrove - 2BHK Elite",
      "property_type": "Apartment",
      "bhk": 2,
      "price": 8500000,
      "sqft": 1150,
      "location": "Perungudi, OMR",
      "city": "Chennai",
      "facing": "North-East",
      "floor": "3rd of 14 Floors",
      "property_status": "Ready to Move",
      "description": "Premium 2BHK apartment with Italian marble flooring and modular kitchen.",
      "amenities": ["Clubhouse", "Swimming Pool", "Gymnasium", "24/7 Security"],
      "image_url": "/api/assets/images/Bedroom.jpg",
      "details": [
        "Master Bedroom: 13'0\" x 11'0\" with attached bath",
        "Living & Dining: 18'6\" x 11'6\" with wide balcony"
      ],
      "room_tiles": [
        {
          "id": "tile-living",
          "name": "Living & Dining",
          "category": "living",
          "dimension": "18'6\" x 11'6\"",
          "spec": "Vitrified tiles, double glazed windows",
          "imageUrl": "/api/assets/images/Bedroom.jpg"
        }
      ]
    }
  ],
  "images": [],
  "image_filter": null,
  "sources": [
    "2BHK + 2T Model House Script - Casagrand Aquagrove.pdf (Page 2)"
  ]
}
```

---

### 2.4. Customer Enquiry Submission
- **Route:** `POST /api/enquiries`
- **Purpose:** Persist customer contact details for site visit bookings or brochure downloads.
- **Request Body (`EnquiryRequest`):**
```json
{
  "name": "Jane Doe",
  "phone": "+91 98765 43210",
  "property_id": "PROP-2BHK-01",
  "message": "Interested in booking a weekend site visit.",
  "consent": true
}
```
- **Response `200 OK`:**
```json
{
  "status": "success",
  "message": "Enquiry submitted successfully",
  "enquiry_id": 14
}
```

---

### 2.5. Document List & Ingestion
- **Route:** `GET /api/documents`
- **Purpose:** List indexed architectural/engineering documents.
- **Response `200 OK`:**
```json
{
  "status": "success",
  "count": 5,
  "documents": [
    {
      "source": "Casagrand_Aquagrove_Specifications.pdf",
      "type": "unstructured_pdf",
      "pages": 12,
      "indexed_at": "2026-11-24T10:00:00Z"
    },
    {
      "source": "Chennai_Properties.xlsx",
      "type": "structured_excel",
      "records": 48,
      "indexed_at": "2026-11-24T10:00:00Z"
    }
  ]
}
```

- **Route:** `POST /api/documents/upload`
- **Purpose:** Administrative document upload to S3 and automated re-indexing.
- **Query Params:** `filename=sample.pdf`
- **Request Body:** Raw binary stream.
- **Response `200 OK`:**
```json
{
  "status": "success",
  "message": "Document uploaded and indexed successfully",
  "filename": "sample.pdf",
  "chunks_added": 24
}
```

---

### 2.6. Image Assets
- **Route:** `GET /api/assets/images`
- **Query Params:** `category` (optional, e.g. `bedroom`, `living`, `bathroom`)
- **Response `200 OK`:**
```json
{
  "status": "success",
  "count": 4,
  "images": [
    {
      "filename": "Bedroom.jpg",
      "category": "bedroom",
      "property_name": "Casagrand Aquagrove",
      "url": "/api/assets/images/Bedroom.jpg"
    }
  ]
}
```

- **Route:** `GET /api/assets/images/{filename}`
- **Purpose:** Static file delivery of JPEG/PNG property photos.
- **Response:** Binary image (`image/jpeg` or `image/png`).

