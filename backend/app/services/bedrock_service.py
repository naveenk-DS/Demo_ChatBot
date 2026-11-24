"""
Amazon Bedrock Service for EstateAI.
Responsible for:
1. Question understanding and intent classification.
2. Structured filter extraction (validated via Pydantic SearchFilters).
3. Embedding generation using Amazon Titan Text Embeddings v2 (amazon.titan-embed-text-v2:0, 1024 dims).
4. Grounded question answering over retrieved PDF chunks and verified property records.
5. Error handling, retries with exponential backoff for throttling, and token usage logging.
Uses Boto3 and Bedrock Runtime Converse API.
Uses standard EC2 IAM instance role credentials.
"""

import json
import logging
import os
from pathlib import Path
import re
import time
from typing import Any, Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError, ConnectTimeoutError, ReadTimeoutError, EndpointConnectionError

from app.config import env, int_env, bool_env
from app.schemas import SearchFilters

logger = logging.getLogger("estateai.bedrock_service")

# Default Bedrock model IDs
DEFAULT_CHAT_MODEL = "anthropic.claude-3-sonnet-20240229-v1:0"
DEFAULT_EMBEDDING_MODEL = "amazon.titan-embed-text-v2:0"
DEFAULT_EMBEDDING_DIMENSIONS = 1024

# Fast client timeout configuration (prevents hanging in offline or local test environments)
BEDROCK_CLIENT_CONFIG = Config(
    connect_timeout=2,
    read_timeout=8,
    retries={"max_attempts": 2, "mode": "standard"},
)

FILTER_EXTRACTION_SYSTEM_PROMPT = """You are an expert real-estate query understanding system for EstateAI, a premium property concierge in Chennai, India.
Analyze the user's message and conversation history to extract structured search filters and intent.

Available Intents:
- "property_search": User is searching for properties (e.g. by BHK, price, location).
- "document_qa": User is asking about architectural/engineering specifications, civil rules, maintenance, plumbing, electrical, handover policies.
- "media_request": User is requesting photos or images (e.g. "show bedroom photos", "pictures of kitchen").
- "contact_request": User wants to schedule a site visit, request a brochure, or contact an agent.
- "general_question": Greetings, polite conversation, or general platform capabilities.
- "search_refinement": Refinements to an existing search (e.g. "under 1 crore", "only north facing").

Locations: Locations are in Chennai (e.g. OMR, Perungudi, Sholinganallur, Guindy, Anna Nagar, Thoraipakkam, Navalur, Kotturpuram).
Price parsing: 1 Crore = 10,000,000 INR; 1 Lakh = 100,000 INR. If user mentions "under 1.5 Cr", max_price is 15000000.

Output MUST be a single raw valid JSON object with these exact keys:
{
  "intent": "property_search" | "document_qa" | "media_request" | "contact_request" | "general_question" | "search_refinement",
  "location": string or null,
  "city": "Chennai",
  "bhk": integer (1 to 10) or null,
  "min_price": integer in INR or null,
  "max_price": integer in INR or null,
  "property_type": string or null,
  "needs_clarification": boolean,
  "clarification_question": string or null,
  "assistant_message": string
}
Do not include markdown fences, comments, or explanations. Return JSON only."""


class BedrockService:
    def __init__(
        self,
        region_name: Optional[str] = None,
        chat_model_id: Optional[str] = None,
        embedding_model_id: Optional[str] = None,
        embedding_dimensions: Optional[int] = None,
    ):
        self.region_name = region_name or env("AWS_REGION", "ap-south-1")
        self.chat_model_id = chat_model_id or env("BEDROCK_CHAT_MODEL_ID", DEFAULT_CHAT_MODEL)
        self.embedding_model_id = embedding_model_id or env("BEDROCK_EMBEDDING_MODEL_ID", DEFAULT_EMBEDDING_MODEL)
        self.embedding_dimensions = embedding_dimensions or int_env("BEDROCK_EMBEDDING_DIMENSIONS", DEFAULT_EMBEDDING_DIMENSIONS)
        
        self._bedrock_client = None
        self._has_credentials = None

    def has_credentials(self) -> bool:
        """Returns True if valid AWS credentials or EC2 IAM role are discoverable."""
        if self._has_credentials is not None:
            return self._has_credentials

        # 1. Check explicit AWS environment variables
        if os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
            self._has_credentials = True
            return True

        # 2. Check if running inside AWS container or EC2
        if os.getenv("AWS_EXECUTION_ENV") or os.getenv("ECS_CONTAINER_METADATA_URI"):
            self._has_credentials = True
            return True

        # 3. Check local ~/.aws credentials or config
        aws_dir = Path.home() / ".aws"
        if (aws_dir / "credentials").exists() or (aws_dir / "config").exists():
            self._has_credentials = True
            return True

        # 4. Check if IMDS is enabled and reachable quickly
        if not bool_env("AWS_EC2_METADATA_DISABLED", True):
            try:
                session = boto3.Session(region_name=self.region_name)
                self._has_credentials = session.get_credentials() is not None
                return self._has_credentials
            except Exception:
                pass

        self._has_credentials = False
        return False

    def _get_client(self):
        """Initializes Bedrock Runtime client using EC2 IAM instance role credentials."""
        if self._bedrock_client is not None:
            return self._bedrock_client

        session_kwargs = {"region_name": self.region_name}
        profile = env("AWS_PROFILE", "")
        if profile and profile not in ("your-aws-profile-name", "realestate-demo"):
            session_kwargs["profile_name"] = profile

        session = boto3.Session(**session_kwargs)
        self._bedrock_client = session.client("bedrock-runtime", config=BEDROCK_CLIENT_CONFIG)
        return self._bedrock_client

    def _execute_with_retry(self, api_func, *args, max_retries: int = 2, **kwargs):
        """Executes a boto3 bedrock-runtime call with exponential backoff for throttling or temporary failures."""
        last_error = None
        for attempt in range(max_retries):
            try:
                return api_func(*args, **kwargs)
            except (EndpointConnectionError, ConnectTimeoutError, NoCredentialsError) as exc:
                # Fast fail if offline or credentials unconfigured
                raise exc
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code", "")
                last_error = exc
                if code in ("ThrottlingException", "RequestLimitExceeded", "TooManyRequestsException", "ModelTimeoutException"):
                    sleep_time = (2 ** attempt) * 0.5
                    logger.warning("Bedrock API throttled (%s). Retrying in %.2fs (attempt %d/%d)", code, sleep_time, attempt + 1, max_retries)
                    time.sleep(sleep_time)
                else:
                    logger.error("Bedrock ClientError [%s]: %s", code, exc)
                    raise
            except Exception as exc:
                last_error = exc
                logger.error("Unexpected error calling Bedrock API: %s", exc)
                raise
        raise last_error

    # =========================================================================
    # 1. EMBEDDING GENERATION (Titan Text Embeddings v2)
    # =========================================================================

    def generate_embedding(self, text: str) -> list[float]:
        """
        Generates 1024-dimensional normalized vector embedding for text using Amazon Titan v2.
        Returns a non-zero vector or raises controlled error. Never generates placeholder zero vectors.
        """
        cleaned = text.strip()
        if not cleaned:
            raise ValueError("Cannot generate embedding for empty text string.")

        if not self.has_credentials():
            raise RuntimeError("AWS Bedrock credentials not present locally. Embedding generation skipped.")

        client = self._get_client()
        payload = {
            "inputText": cleaned[:8000],  # Titan v2 max input limit
            "dimensions": self.embedding_dimensions,
            "normalize": True,
        }

        def _call_invoke():
            response = client.invoke_model(
                modelId=self.embedding_model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(payload),
            )
            resp_body = json.loads(response["body"].read().decode("utf-8"))
            embedding = resp_body.get("embedding")
            if not embedding or not isinstance(embedding, list) or len(embedding) != self.embedding_dimensions:
                raise ValueError(f"Invalid embedding returned from Bedrock: expected {self.embedding_dimensions} dimensions")
            return embedding

        try:
            return self._execute_with_retry(_call_invoke)
        except Exception as exc:
            logger.error("Failed to generate embedding with Bedrock model '%s': %s", self.embedding_model_id, exc)
            raise

    # =========================================================================
    # 2. QUESTION UNDERSTANDING & FILTER EXTRACTION
    # =========================================================================

    def extract_filters(self, message: str, history: Optional[list[dict[str, str]]] = None) -> SearchFilters:
        """
        Understands user question, identifies intent, extracts structured filters,
        and returns a validated Pydantic SearchFilters object.
        """
        if not self.has_credentials():
            logger.debug("AWS credentials not present locally. Using rule-based query extractor.")
            return self._fallback_filter_extractor(message)

        history_text = ""
        if history:
            recent = history[-4:]
            formatted = [f"{m.get('role', 'user').capitalize()}: {m.get('content', '')}" for m in recent]
            history_text = "\nRecent Conversation:\n" + "\n".join(formatted) + "\n"

        prompt = f"{history_text}User: {message}\n\nExtract search filters and intent as JSON:"

        system_prompts = [{"text": FILTER_EXTRACTION_SYSTEM_PROMPT}]
        messages = [{"role": "user", "content": [{"text": prompt}]}]

        try:
            client = self._get_client()
            response = self._execute_with_retry(
                client.converse,
                modelId=self.chat_model_id,
                system=system_prompts,
                messages=messages,
                inferenceConfig={"maxTokens": 400, "temperature": 0.1},
            )

            # Log token usage
            usage = response.get("usage", {})
            logger.info("Bedrock filter extraction tokens: in=%s, out=%s", usage.get("inputTokens"), usage.get("outputTokens"))

            output_text = response.get("output", {}).get("message", {}).get("content", [{}])[0].get("text", "")
            
            # Clean JSON string
            cleaned_json = output_text.strip()
            if cleaned_json.startswith("```"):
                cleaned_json = re.sub(r"^```(?:json)?\s*", "", cleaned_json)
                cleaned_json = re.sub(r"\s*```$", "", cleaned_json)

            data = json.loads(cleaned_json)
            validated = SearchFilters(**data)
            return validated

        except Exception as exc:
            logger.warning("Bedrock converse filter extraction fallback due to: %s. Using rule-based extractor.", exc)
            return self._fallback_filter_extractor(message)

    def _fallback_filter_extractor(self, text: str) -> SearchFilters:
        """Deterministic regex fallback for query understanding when Bedrock is offline."""
        lowered = text.lower().strip()
        
        # Check greetings
        if re.search(r"^(hi|hello|hey|good\s+morning|good\s+afternoon|good\s+evening)\b", lowered):
            return SearchFilters(
                intent="general_question",
                assistant_message="Hello! Welcome to EstateAI Concierge. How can I help you find your ideal property in Chennai today?",
            )

        # Check media request
        if any(w in lowered for w in ("photo", "photos", "image", "images", "picture", "pictures", "view photos")):
            return SearchFilters(intent="media_request")

        # Check contact / enquiry
        if any(w in lowered for w in ("site visit", "book visit", "schedule", "enquiry", "brochure", "contact agent")):
            return SearchFilters(intent="contact_request")

        # Check document QA keywords
        if any(w in lowered for w in ("specification", "specs", "dimension", "dimensions", "flooring", "paint", "wiring", "plumbing", "rules", "handover", "maintenance", "ceiling")):
            # If BHK is mentioned, it's a combined document question
            m_bhk = re.search(r"\b([1-9]|10)\s*(?:bhk|bed|bedroom)?\b", lowered)
            bhk_val = int(m_bhk.group(1)) if m_bhk else None
            return SearchFilters(intent="document_qa", bhk=bhk_val)

        # Property search extraction
        m_bhk = re.search(r"\b([1-9]|10)\s*(?:bhk|bed|bedroom)?\b", lowered)
        bhk_val = int(m_bhk.group(1)) if m_bhk else None

        # Price parsing
        max_price = None
        m_cr = re.search(r"(?:under|below|within|upto|less\s+than)\s*([\d\.]+)\s*(?:cr|crore|crores)", lowered)
        if m_cr:
            try:
                max_price = int(float(m_cr.group(1)) * 10_000_000)
            except ValueError:
                pass
        if not max_price:
            m_l = re.search(r"(?:under|below|within|upto|less\s+than)\s*([\d\.]+)\s*(?:l|lakh|lakhs)", lowered)
            if m_l:
                try:
                    max_price = int(float(m_l.group(1)) * 100_000)
                except ValueError:
                    pass

        # Location extraction
        loc = None
        for known_loc in ("perungudi", "omr", "sholinganallur", "guindy", "anna nagar", "thoraipakkam", "navalur", "kotturpuram", "porur", "adyar"):
            if known_loc in lowered:
                loc = known_loc.title()
                break

        return SearchFilters(
            intent="property_search",
            bhk=bhk_val,
            max_price=max_price,
            location=loc,
            city="Chennai",
        )

    # =========================================================================
    # 3. GROUNDED ANSWER SYNTHESIS (Converse API)
    # =========================================================================

    def generate_grounded_answer(
        self,
        query: str,
        retrieved_chunks: list[dict[str, Any]],
        properties: Optional[list[dict[str, Any]]] = None,
        history: Optional[list[dict[str, str]]] = None,
    ) -> str:
        """
        Synthesizes a professional, grounded assistant answer based strictly on verified
        property records and retrieved document chunks. Does not hallucinate unverified facts.
        """
        # Format verified property context
        prop_context = ""
        if properties:
            lines = []
            for p in properties:
                lines.append(
                    f"- {p.get('property_name', 'Property')} ({p.get('bhk', '')} BHK): "
                    f"Price: Rs. {p.get('price', 0):,}, Area: {p.get('sqft', '')} sq.ft, "
                    f"Location: {p.get('location', '')}, Facing: {p.get('facing', '')}, Status: {p.get('property_status', '')}."
                )
            prop_context = "VERIFIED MATCHING PROPERTIES FROM DATABASE:\n" + "\n".join(lines) + "\n\n"

        # Format retrieved document chunks
        doc_context = ""
        if retrieved_chunks:
            lines = []
            for idx, c in enumerate(retrieved_chunks, 1):
                src = c.get("source", "Document")
                page = c.get("page", 1)
                text = c.get("text", "").strip()
                lines.append(f"[{idx}] Source: {src} (Page {page}):\n{text}")
            doc_context = "DOCUMENTED ARCHITECTURAL & ENGINEERING SPECIFICATIONS:\n" + "\n\n".join(lines) + "\n\n"

        system_instruction = (
            "You are EstateAI Concierge, an intelligent, professional real estate assistant representing verified properties in Chennai. "
            "Your answers must be grounded strictly in the provided verified property records and architectural specification documents. "
            "Never invent property prices, specifications, or rules not present in the context. "
            "Keep your explanations concise, professional, and well-formatted with markdown bullet points."
        )

        user_content = (
            f"{prop_context}{doc_context}"
            f"User Question: {query}\n\n"
            f"Provide a helpful, grounded response referencing the verified facts."
        )

        messages = []
        if history:
            for m in history[-3:]:
                role = m.get("role", "user")
                if role in ("user", "assistant"):
                    messages.append({"role": role, "content": [{"text": m.get("content", "")}]})

        messages.append({"role": "user", "content": [{"text": user_content}]})

        if not self.has_credentials():
            logger.debug("AWS credentials not present locally. Using deterministic grounded answer.")
            if properties:
                names = ", ".join([p.get("property_name", "") for p in properties[:2]])
                return f"Here are the verified properties matching your request: {names}. You can explore the complete specifications, floor plans, and amenities in the cards below."
            return "Here are the relevant details extracted from the verified property documents."

        try:
            client = self._get_client()
            response = self._execute_with_retry(
                client.converse,
                modelId=self.chat_model_id,
                system=[{"text": system_instruction}],
                messages=messages,
                inferenceConfig={"maxTokens": 600, "temperature": 0.2},
            )

            usage = response.get("usage", {})
            logger.info("Bedrock synthesis tokens: in=%s, out=%s", usage.get("inputTokens"), usage.get("outputTokens"))

            answer = response.get("output", {}).get("message", {}).get("content", [{}])[0].get("text", "")
            return answer.strip()

        except Exception as exc:
            logger.warning("Bedrock converse answer generation failed: %s. Using structured fallback response.", exc)
            if properties:
                names = ", ".join([p.get("property_name", "") for p in properties[:2]])
                return f"Here are the verified properties matching your request: {names}. You can explore the complete specifications, floor plans, and amenities in the cards below."
            return "Here are the relevant details extracted from the verified property documents."

