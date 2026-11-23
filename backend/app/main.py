import logging
import re
from typing import Optional
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .config import env
from .schemas import ChatRequest, EnquiryRequest, SearchFilters
from .llm import understand
from .sql_builder import build_sql
from .sql_validator import validate_generated_sql
from .athena import run_query
from .enquiries import save_enquiry
from .rag.service import answer_question
from .rag.store import sync_pdf_documents
from .rag.loader import get_default_pdf_dir
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


def _rag_to_details(rag_answer: str, query: str = "") -> list[str]:
    """Convert a RAG markdown answer into concise detail items for property card 'details' field.
    Filters and prioritizes details based on query topic (e.g. bedroom, kitchen, bathroom,
    amenities, doors/windows, electrical, flooring) when a specific topic is queried.
    Strips markdown formatting and keeps items concise, readable, and professional."""
    if not rag_answer:
        return []

    raw_items = []
    for line in rag_answer.splitlines():
        # Remove markdown bold/italic/headers
        clean = re.sub(r"[*_#`]+", "", line).strip()
        # Strip leading list markers: -, *, •, 1., 2. etc.
        clean = re.sub(r"^[-•*]\s+", "", clean)
        clean = re.sub(r"^\d+\.\s+", "", clean)
        clean = clean.strip()
        if len(clean) >= 4 and not clean.lower().startswith("i couldn") and not clean.lower().startswith("here are"):
            raw_items.append(clean[:130])

    if not raw_items:
        return []

    q_lower = query.lower().strip() if query else ""

    # Topic-specific keywords map
    topic_keywords = {
        "bedroom": ["bedroom", "master bed", "guest bed", "kids bed", "wardrobe", "dimension"],
        "kitchen": ["kitchen", "granite", "sink", "utility", "counter", "chimney", "pipe", "gas", "hob"],
        "bathroom": ["bathroom", "toilet", "sanitary", "cp fitting", "c.p.", "shower", "geyser", "kohler", "toto", "jaguar"],
        "living": ["living", "dining", "foyer", "balcony", "deck", "patio", "terrace"],
        "doors_windows": ["door", "window", "frame", "shutter", "hardware", "lock", "upvc", "glass", "grill"],
        "flooring": ["flooring", "tile", "tiles", "vitrified", "granite", "marble", "skirting", "wooden"],
        "electrical": ["electrical", "wiring", "wire", "switch", "schneider", "havells", "mcb", "ac point", "power backup", "generator", "inverter"],
        "amenities": ["amenit", "clubhouse", "swimming", "pool", "gym", "court", "badminton", "indoor", "jogging", "garden", "play area"],
        "parking": ["parking", "car park", "ev charging", "driveway", "traffic", "slot"],
        "plumbing": ["plumbing", "pipe", "drainage", "sewage", "stp", "water supply", "tank"],
    }

    # Detect user's focused topic
    matched_topics = [t for t, kws in topic_keywords.items() if any(kw in q_lower for kw in kws)]

    if matched_topics:
        target_kws = [kw for t in matched_topics for kw in topic_keywords[t]]
        filtered = [item for item in raw_items if any(kw in item.lower() for kw in target_kws)]
        if filtered:
            return filtered[:12]

    # If no specific topic matched or filter yielded no results, return clean items
    return raw_items[:12]


def extract_chennai_location(text: str) -> Optional[str]:
    """Extract recognized Chennai localities from user text."""
    locs = [
        "anna nagar", "velachery", "porur", "guindy", "medavakkam",
        "perungudi", "sholinganallur", "kelambakkam", "navalur", "omr",
        "ecr", "adyar", "t nagar", "besant nagar", "thiruvanmiyur"
    ]
    lower = text.lower()
    for loc in locs:
        if loc in lower:
            return loc
    return None


DEMO_PROPERTY_CATALOG = {
    1: [
        {
            "property_id": "PROP-1BHK-01",
            "property_name": "Harbour Smart Suites",
            "property_type": "Apartment",
            "bhk": 1,
            "price": 4200000,
            "sqft": 620,
            "location": "Sholinganallur, OMR",
            "city": "Chennai",
            "facing": "East facing",
            "floor": "4th",
            "property_status": "Ready to move",
            "description": "Compact luxury 1 BHK studio suite with modern modular kitchenette, private Juliet balcony, and smart home provisions. High rental yield asset near major IT parks.",
            "amenities": ["Gym", "Coworking Lounge", "Rooftop Garden", "Power Backup"],
            "image_url": None,
        },
        {
            "property_id": "PROP-1BHK-02",
            "property_name": "Palm Crest Suites",
            "property_type": "Apartment",
            "bhk": 1,
            "price": 4500000,
            "sqft": 660,
            "location": "Kelambakkam, OMR",
            "city": "Chennai",
            "facing": "North facing",
            "floor": "6th",
            "property_status": "Handover Jun 2026",
            "description": "Contemporary studio apartment designed for modern professionals. Panoramic views of lake and lush greenery with clubhouse access.",
            "amenities": ["Clubhouse", "Swimming Pool", "EV Charging", "24/7 Security"],
            "image_url": None,
        },
        {
            "property_id": "PROP-1BHK-03",
            "property_name": "Metroline Studio",
            "property_type": "Apartment",
            "bhk": 1,
            "price": 4800000,
            "sqft": 580,
            "location": "Guindy",
            "city": "Chennai",
            "facing": "North-East facing",
            "floor": "3rd",
            "property_status": "Ready to move",
            "description": "Prime location urban 1 BHK apartment situated next to Guindy Metro and Kathipara junction. Excellent connectivity to airport and central business districts.",
            "amenities": ["Fitness Center", "EV Charging", "Lift", "CCTV Security"],
            "image_url": None,
        },
        {
            "property_id": "PROP-1BHK-04",
            "property_name": "Grand Urban Suites",
            "property_type": "Apartment",
            "bhk": 1,
            "price": 5200000,
            "sqft": 650,
            "location": "Velachery",
            "city": "Chennai",
            "facing": "East facing",
            "floor": "5th",
            "property_status": "Ready to move",
            "description": "Smartly designed 1 BHK near Phoenix Marketcity with modern interiors, piped gas, and round-the-clock water and power backup.",
            "amenities": ["Clubhouse", "Covered Car Parking", "Power Backup", "Gym"],
            "image_url": None,
        },
    ],
    2: [
        {
            "property_id": "PROP-2BHK-01",
            "property_name": "Harbour Reach",
            "property_type": "Apartment",
            "bhk": 2,
            "price": 8200000,
            "sqft": 1180,
            "location": "Sholinganallur, OMR",
            "city": "Chennai",
            "facing": "East facing",
            "floor": "9th",
            "property_status": "Ready to move",
            "description": "Spacious two-bedroom home with well-ventilated living room, wide covered balcony, and vitrified finishes. Close to top international schools and metro station.",
            "amenities": ["Clubhouse", "Swimming Pool", "Gym", "Jogging Track"],
            "image_url": None,
        },
        {
            "property_id": "PROP-2BHK-02",
            "property_name": "Palm Breeze Residences",
            "property_type": "Apartment",
            "bhk": 2,
            "price": 7900000,
            "sqft": 1120,
            "location": "Perungudi, OMR",
            "city": "Chennai",
            "facing": "North facing",
            "floor": "11th",
            "property_status": "Ready to move",
            "description": "High-rise modern 2 BHK overlooking central landscaped courtyard. Premium German sanitaryware, FRLS concealed wiring, and dedicated covered car park.",
            "amenities": ["Sky Lounge", "Badminton Court", "Kids Play Area", "Power Backup"],
            "image_url": None,
        },
        {
            "property_id": "PROP-2BHK-03",
            "property_name": "Emerald Park Residences",
            "property_type": "Apartment",
            "bhk": 2,
            "price": 9800000,
            "sqft": 1220,
            "location": "Anna Nagar",
            "city": "Chennai",
            "facing": "East facing",
            "floor": "4th",
            "property_status": "Ready to move",
            "description": "Prestigious 2 BHK in prime Anna Nagar neighborhood with tree-lined avenues, top schools, metro access, and high-end vitrified tile flooring.",
            "amenities": ["Clubhouse", "Gym", "Landscaped Garden", "24/7 Security"],
            "image_url": None,
        },
        {
            "property_id": "PROP-2BHK-04",
            "property_name": "Lakeview Heights",
            "property_type": "Apartment",
            "bhk": 2,
            "price": 8500000,
            "sqft": 1150,
            "location": "Velachery",
            "city": "Chennai",
            "facing": "North-East facing",
            "floor": "7th",
            "property_status": "Ready to move",
            "description": "Well-ventilated 2 BHK close to Velachery MRTS and Phoenix Marketcity. Features modular kitchen provision and premium bathroom fittings.",
            "amenities": ["Swimming Pool", "Gym", "Kids Play Area", "Power Backup"],
            "image_url": None,
        },
        {
            "property_id": "PROP-2BHK-05",
            "property_name": "Orchid Enclave",
            "property_type": "Apartment",
            "bhk": 2,
            "price": 7400000,
            "sqft": 1080,
            "location": "Porur",
            "city": "Chennai",
            "facing": "East facing",
            "floor": "5th",
            "property_status": "Ready to move",
            "description": "Quiet gated community 2 BHK located off Mount-Poonamallee Road near Ramachandra Hospital and DLF IT Park.",
            "amenities": ["Clubhouse", "Badminton Court", "Covered Car Park", "CCTV"],
            "image_url": None,
        },
        {
            "property_id": "PROP-2BHK-06",
            "property_name": "Green Meadows",
            "property_type": "Apartment",
            "bhk": 2,
            "price": 6800000,
            "sqft": 1020,
            "location": "Medavakkam",
            "city": "Chennai",
            "facing": "North facing",
            "floor": "3rd",
            "property_status": "Ready to move",
            "description": "Affordable luxury 2 BHK on Medavakkam-Sholinganallur main link road with easy access to both OMR IT corridor and Tambaram.",
            "amenities": ["Gym", "Children Play Area", "Power Backup", "Rooftop Party Area"],
            "image_url": None,
        },
    ],
    3: [
        {
            "property_id": "PROP-3BHK-01",
            "property_name": "Harbour Reach",
            "property_type": "Apartment",
            "bhk": 3,
            "price": 16800000,
            "sqft": 1620,
            "location": "Sholinganallur, OMR",
            "city": "Chennai",
            "facing": "East facing",
            "floor": "18th",
            "property_status": "Ready to move",
            "description": "Move in now. A high-floor east-facing home with morning light and a skyline balcony. The project is high-rise with wide balconies and glass railings.",
            "amenities": ["Sky lounge", "Pool", "Gym"],
            "image_url": None,
        },
        {
            "property_id": "PROP-3BHK-02",
            "property_name": "Palm Grove Villas",
            "property_type": "Villa",
            "bhk": 3,
            "price": 13500000,
            "sqft": 1890,
            "location": "Kelambakkam, OMR",
            "city": "Chennai",
            "facing": "East facing",
            "floor": "G+1",
            "property_status": "Handover Sep 2027",
            "description": "A three-bedroom villa with its own garden, in a gated lane close to the coast. The project is gated villas with sloped roofs and a private garden.",
            "amenities": ["Clubhouse", "Pool", "Jogging track"],
            "image_url": None,
        },
        {
            "property_id": "PROP-3BHK-03",
            "property_name": "Royal Palms",
            "property_type": "Apartment",
            "bhk": 3,
            "price": 19500000,
            "sqft": 1780,
            "location": "Anna Nagar",
            "city": "Chennai",
            "facing": "North-East facing",
            "floor": "6th",
            "property_status": "Ready to move",
            "description": "Exclusive luxury 3 BHK in central Anna Nagar with spacious living-dining, Italian marble flooring in living room, and 2 covered car parks.",
            "amenities": ["Infinity Pool", "Clubhouse", "Gym", "Concierge"],
            "image_url": None,
        },
        {
            "property_id": "PROP-3BHK-04",
            "property_name": "Grand Galleria",
            "property_type": "Apartment",
            "bhk": 3,
            "price": 15500000,
            "sqft": 1650,
            "location": "Velachery",
            "city": "Chennai",
            "facing": "East facing",
            "floor": "10th",
            "property_status": "Ready to move",
            "description": "Premium 3 BHK home overlooking lake view in Velachery, complete with wooden flooring in master bedroom and large terrace balcony.",
            "amenities": ["Clubhouse", "Pool", "Tennis Court", "Power Backup"],
            "image_url": None,
        },
        {
            "property_id": "PROP-3BHK-05",
            "property_name": "Skyline Crest",
            "property_type": "Apartment",
            "bhk": 3,
            "price": 12800000,
            "sqft": 1540,
            "location": "Porur",
            "city": "Chennai",
            "facing": "North facing",
            "floor": "8th",
            "property_status": "Ready to move",
            "description": "Modern 3 BHK apartment in gated township close to DLF Cybercity and Porur junction, featuring high ceilings and private balcony.",
            "amenities": ["Clubhouse", "Gym", "Jogging Track", "Kids Play Area"],
            "image_url": None,
        },
        {
            "property_id": "PROP-3BHK-06",
            "property_name": "Serene Woods",
            "property_type": "Apartment",
            "bhk": 3,
            "price": 18500000,
            "sqft": 1720,
            "location": "Guindy",
            "city": "Chennai",
            "facing": "East facing",
            "floor": "12th",
            "property_status": "Ready to move",
            "description": "Ultra-convenient 3 BHK overlooking Guindy National Park green canopy, situated near Guindy Race Course and Five Furlong Road.",
            "amenities": ["Rooftop Pool", "Fitness Suite", "Sky Lounge", "24/7 Concierge"],
            "image_url": None,
        },
    ],
    4: [
        {
            "property_id": "PROP-4BHK-01",
            "property_name": "Skyline Towers",
            "property_type": "Penthouse",
            "bhk": 4,
            "price": 31000000,
            "sqft": 3450,
            "location": "Sholinganallur, OMR",
            "city": "Chennai",
            "facing": "North-East facing",
            "floor": "24th",
            "property_status": "Handover Dec 2026",
            "description": "Ultra-luxury double-height penthouse sky villa with imported Italian Botticino marble, private 350 sq ft open terrace deck, and private Jacuzzi provision.",
            "amenities": ["Infinity Pool", "Private Terrace Deck", "Concierge Service", "Home Cinema Lounge"],
            "image_url": None,
        },
        {
            "property_id": "PROP-4BHK-02",
            "property_name": "Palm Grove Royal Villas",
            "property_type": "Villa",
            "bhk": 4,
            "price": 24500000,
            "sqft": 2850,
            "location": "Kelambakkam, OMR",
            "city": "Chennai",
            "facing": "East facing",
            "floor": "G+2",
            "property_status": "Handover Sep 2027",
            "description": "Four-bedroom triplex coastal villa with private 450 sq ft landscaped garden, dual SUV covered carport with EV fast charger, and rooftop party pergola.",
            "amenities": ["Private Garden", "Rooftop Pergola", "EV Charging", "Clubhouse Access"],
            "image_url": None,
        },
        {
            "property_id": "PROP-4BHK-03",
            "property_name": "Imperial Sovereign",
            "property_type": "Apartment",
            "bhk": 4,
            "price": 38000000,
            "sqft": 3600,
            "location": "Anna Nagar",
            "city": "Chennai",
            "facing": "North facing",
            "floor": "14th",
            "property_status": "Ready to move",
            "description": "Signature 4 BHK luxury residence in Anna Nagar with private elevator lobby, Italian marble flooring, servant quarters, and 3 covered car parks.",
            "amenities": ["Heated Pool", "Clubhouse", "Spa", "Banquet Hall", "Concierge"],
            "image_url": None,
        },
        {
            "property_id": "PROP-4BHK-04",
            "property_name": "Sovereign Heights",
            "property_type": "Penthouse",
            "bhk": 4,
            "price": 32500000,
            "sqft": 3200,
            "location": "Guindy",
            "city": "Chennai",
            "facing": "East facing",
            "floor": "16th",
            "property_status": "Ready to move",
            "description": "Palatial 4 BHK penthouse with breathtaking views of the city skyline, private rooftop deck, smart home automation, and dedicated visitor parking.",
            "amenities": ["Infinity Pool", "Private Deck", "Gym", "EV Fast Charging"],
            "image_url": None,
        },
        {
            "property_id": "PROP-4BHK-05",
            "property_name": "Emerald Manor",
            "property_type": "Villa",
            "bhk": 4,
            "price": 26500000,
            "sqft": 2900,
            "location": "Porur",
            "city": "Chennai",
            "facing": "East facing",
            "floor": "G+2",
            "property_status": "Ready to move",
            "description": "Independent 4 BHK gated community luxury villa with private landscaped backyard, solar water heating, and modern club facilities.",
            "amenities": ["Private Garden", "Clubhouse", "Swimming Pool", "24/7 Security"],
            "image_url": None,
        },
    ],
}


def _fetch_properties_for_bhk(bhk_num: Optional[int], limit: int = 2, location: Optional[str] = None) -> list[dict]:
    """Fetch up to `limit` property records for a given BHK from Athena.
    Falls back gracefully to demo catalog if Athena query returns no rows or fails."""
    from .schemas import SearchFilters
    records = []
    if bhk_num:
        try:
            sf = SearchFilters(intent="property_search", bhk=bhk_num, location=location)
            sql = build_sql(sf)
            sql = re.sub(r"LIMIT\s+\d+", f"LIMIT {limit}", sql)
            validate_generated_sql(sql)
            records = run_query(sql)
        except Exception as exc:
            logger.debug("Athena query for BHK=%s failed: %s", bhk_num, exc)
            records = []

    # If Athena returned records, use them
    if records:
        return records[:limit]

    # Graceful fallback: return matching properties from the demo catalog for the BHK & location
    target_bhk = bhk_num if bhk_num in DEMO_PROPERTY_CATALOG else 3
    demo_cards = DEMO_PROPERTY_CATALOG.get(target_bhk, DEMO_PROPERTY_CATALOG[3])
    import copy
    copied = copy.deepcopy(demo_cards)
    if location:
        loc_l = location.lower().strip()
        matched = [
            p for p in copied
            if loc_l in p.get("location", "").lower() or loc_l in p.get("description", "").lower()
        ]
        if matched:
            return matched[:limit]
    return copied[:limit]


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


@app.get("/api/documents")
def list_documents():
    """Returns catalog of indexed PDF documents in the knowledge base."""
    pdf_dir = get_default_pdf_dir()
    if not pdf_dir.exists():
        return {"status": "success", "documents": [], "total": 0}
    docs = []
    for f in sorted(pdf_dir.glob("*.pdf")):
        docs.append({
            "filename": f.name,
            "size_bytes": f.stat().st_size,
        })
    return {"status": "success", "documents": docs, "total": len(docs)}


@app.post("/api/documents/upload")
async def upload_document(request: Request, filename: Optional[str] = None):
    """
    Uploads an arbitrary PDF document into the knowledge base.
    Immediately extracts text, chunks, embeds, and indexes it into ChromaDB.
    Supports multipart form upload or direct binary stream.
    """
    content_type = request.headers.get("content-type", "")
    target_filename = filename or request.headers.get("x-filename")
    content = b""

    if "multipart/form-data" in content_type:
        try:
            form = await request.form()
            file_obj = form.get("file")
            if file_obj:
                target_filename = getattr(file_obj, "filename", target_filename)
                content = await file_obj.read()
        except Exception:
            content = await request.body()
    else:
        content = await request.body()

    if not target_filename:
        target_filename = "Uploaded_Document.pdf"

    if not target_filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files (.pdf) are supported.")

    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file content cannot be empty.")

    pdf_dir = get_default_pdf_dir()
    pdf_dir.mkdir(parents=True, exist_ok=True)
    target_path = pdf_dir / target_filename

    with open(target_path, "wb") as f:
        f.write(content)

    sync_res = sync_pdf_documents()
    return {
        "status": "success",
        "filename": target_filename,
        "size_bytes": len(content),
        "message": f"Successfully uploaded and indexed '{target_filename}'.",
        "sync_details": sync_res,
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

        # FAST-PATH 3: Unambiguous Document QA (specifications, dimensions, comparisons, room counts, entrance, arbitrary documents)
        has_doc_qa_keyword = any(k in user_msg_lower for k in [
            "dimension", "dimensions", "specification", "specifications", "document detail", "document details",
            "entrance feature", "entrance features", "which is better", "compare 2bhk",
            "compare 3bhk", "compare", "all three bedrooms", "three bedrooms", "five bedrooms", "four bedrooms",
            "how many bedrooms", "does the 3bhk have", "does the 2bhk have", "does the 4bhk have",
            "script", "floor plan", "amenities", "amenity",
            "document", "pdf", "file", "agreement", "guideline", "guidelines", "rules", "policy", "policies",
            "terms", "condition", "conditions", "pricing", "cost", "fee", "fees", "clause", "clauses",
            "handbook", "brochure", "timeline", "possession", "maintenance", "security deposit", "parking",
            "clubhouse", "gym", "elevator", "terrace", "balcony",
            "renovation", "interior", "hour", "hours", "pet", "pets", "ev", "structure", "structural",
            "water", "stp", "sewage", "swimming", "sports", "court", "paint", "painting", "lock",
            "doors", "windows", "wire", "wiring", "plumbing", "flooring", "tile", "tiles"
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
            bhk_num = int(config_hint[0]) if config_hint and config_hint[0].isdigit() else None
            loc_hint = extract_chennai_location(user_msg_lower)
            rag_res = answer_question(req.message, configuration=config_hint, provider=req.provider)
            if not rag_res.get("success") or not rag_res.get("sources") or rag_res.get("answer", "").startswith("I couldn't find this information"):
                rag_res_u = answer_question(req.message, configuration=None, provider=req.provider)
                if rag_res_u.get("success") and rag_res_u.get("sources") and not rag_res_u.get("answer", "").startswith("I couldn't find this information"):
                    rag_res = rag_res_u
            if not rag_res.get("success") and rag_res.get("error"):
                err_msg = rag_res.get("error")
                if "timed out" in err_msg.lower() or "timeout" in err_msg.lower():
                    raise HTTPException(status_code=504, detail="The AI provider timed out. Please try again.")
                raise HTTPException(status_code=502, detail=f"AI provider failed: {err_msg}")
            details = _rag_to_details(rag_res.get("answer", ""), query=req.message)
            if bhk_num:
                props = _fetch_properties_for_bhk(bhk_num, limit=2, location=loc_hint)
                for p in props:
                    p["details"] = details
                bhk_label = f"{bhk_num} BHK"
                intro = f"Here are the {bhk_label} details from the property documents."
                return {
                    "status": "success",
                    "assistant_message": intro,
                    "filters": {"intent": "document_qa", "bhk": bhk_num, "location": loc_hint},
                    "properties": props,
                    "result_count": len(props),
                    "images": [],
                    "image_filter": None,
                }
            else:
                # Check if multiple BHK configurations are being compared
                matches = sorted(list(set(re.findall(r"\b([1-9])\s*bhk\b", user_msg_lower))))
                if len(matches) >= 2:
                    comparison_props = []
                    for m in matches[:2]:
                        p_list = _fetch_properties_for_bhk(int(m), limit=1, location=loc_hint)
                        if p_list:
                            p_list[0]["details"] = details
                            comparison_props.append(p_list[0])
                    if comparison_props:
                        return {
                            "status": "success",
                            "assistant_message": f"Here is a side-by-side comparison of {matches[0]} BHK and {matches[1]} BHK specifications.",
                            "filters": {"intent": "document_qa", "bhk": None, "location": loc_hint},
                            "properties": comparison_props,
                            "result_count": len(comparison_props),
                            "images": [],
                            "image_filter": None,
                        }
                return {
                    "status": "message",
                    "assistant_message": rag_res.get("answer", "Here are the relevant details from the property documents."),
                    "filters": {"intent": "document_qa", "bhk": None},
                    "properties": [],
                }

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

        # 3. Search Refinement — refine previous property search using accumulated context
        if filters.intent == "search_refinement":
            records = []
            try:
                sql = build_sql(filters)
                validate_generated_sql(sql)
                records = run_query(sql)
            except Exception as q_err:
                logger.warning("Search refinement query failed: %s", q_err)
                records = []
            if not records:
                loc = filters.location or extract_chennai_location(user_msg_lower)
                records = _fetch_properties_for_bhk(filters.bhk or 3, limit=2, location=loc)
            count_msg = f"Found {len(records)} matching propert{'y' if len(records) == 1 else 'ies'} with your refined criteria."
            return {
                "status": "success",
                "assistant_message": filters.assistant_message or count_msg,
                "filters": filters.model_dump(),
                "properties": records,
                "result_count": len(records),
                "images": [],
                "image_filter": None,
            }

        # 4. Document QA � always return property cards with details injected from RAG
        if filters.intent == "document_qa":
            try:
                config_hint = extract_bhk_config(user_msg_lower, fallback_bhk=filters.bhk)
                bhk_num = int(config_hint[0]) if config_hint and config_hint[0].isdigit() else filters.bhk
                loc_hint = filters.location or extract_chennai_location(user_msg_lower)
                rag_res = answer_question(req.message, configuration=config_hint, provider=req.provider)
                if not rag_res.get("success") or not rag_res.get("sources") or rag_res.get("answer", "").startswith("I couldn't find this information"):
                    rag_res_u = answer_question(req.message, configuration=None, provider=req.provider)
                    if rag_res_u.get("success") and rag_res_u.get("sources") and not rag_res_u.get("answer", "").startswith("I couldn't find this information"):
                        rag_res = rag_res_u
                if rag_res.get("success") and rag_res.get("answer"):
                    details = _rag_to_details(rag_res.get("answer", ""), query=req.message)
                    props = _fetch_properties_for_bhk(bhk_num, limit=2, location=loc_hint)
                    if props:
                        for p in props:
                            p["details"] = details
                        bhk_label = f"{bhk_num} BHK" if bhk_num else "matching"
                        intro = f"Here are the {bhk_label} details from the property documents."
                        return {
                            "status": "success",
                            "assistant_message": intro,
                            "filters": filters.model_dump(),
                            "properties": props,
                            "result_count": len(props),
                            "images": [],
                            "image_filter": None,
                        }
            except Exception as rag_err:
                logger.warning("RAG document_qa failed: %s", rag_err)

        # 5. General question fallback with RAG check
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

        # 6. Clarification required for property search
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

        # 7. Contact request
        if filters.intent == "contact_request":
            return {
                "status": "message",
                "assistant_message": filters.assistant_message or "You can schedule a site visit or submit an inquiry using the enquiry form.",
                "filters": filters.model_dump(),
                "properties": [],
            }

        # 8. Non-search fallback
        if filters.intent != "property_search":
            return {
                "status": "message",
                "assistant_message": filters.assistant_message or "I can help search properties or answer brochure specifications. How can I help?",
                "filters": filters.model_dump(),
                "properties": [],
            }

        # 9. Property Search (SQL + Athena)
        records = []
        try:
            sql = build_sql(filters)
            validate_generated_sql(sql)
            records = run_query(sql)
        except Exception as q_err:
            logger.warning("Property query failed: %s", q_err)
            records = []
        if not records:
            loc = filters.location or extract_chennai_location(user_msg_lower)
            records = _fetch_properties_for_bhk(filters.bhk or 3, limit=2, location=loc)
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
