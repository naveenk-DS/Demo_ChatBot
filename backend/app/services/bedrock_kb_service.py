"""
Amazon Bedrock Knowledge Bases Service for EstateAI.
Responsible for:
1. Connecting to Amazon Bedrock Knowledge Bases via bedrock-agent-runtime.
2. Executing Retrieve API calls over ingested unstructured architectural PDF brochures.
3. Supporting configurable retrieval search types (HYBRID vs SEMANTIC) based on
   vector store capabilities (OpenSearch Serverless, Pinecone, Aurora, etc.).
4. Normalizing Bedrock KB retrieval chunks into standard EstateAI schema.
5. Strict production error handling preventing silent fallback to stale local vectors.
"""

import logging
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, EndpointConnectionError, ConnectTimeoutError

from app.config import env, int_env, bool_env

logger = logging.getLogger("estateai.bedrock_kb_service")

# Timeout config for Bedrock Agent Runtime
KB_CLIENT_CONFIG = Config(
    connect_timeout=3,
    read_timeout=10,
    retries={"max_attempts": 2, "mode": "standard"},
)

VALID_SEARCH_TYPES = ("HYBRID", "SEMANTIC")


PLACEHOLDER_IDS = {"YOUR_BEDROCK_KNOWLEDGE_BASE_ID", "YOUR_KNOWLEDGE_BASE_ID", "none", "null", ""}


class BedrockKnowledgeBaseError(Exception):
    """Raised when an error occurs while communicating with Bedrock Knowledge Bases."""
    pass


class BedrockKnowledgeBaseService:
    def __init__(
        self,
        kb_id: Optional[str] = None,
        region_name: Optional[str] = None,
        search_type: Optional[str] = None,
    ):
        self.kb_id = (kb_id or env("BEDROCK_KNOWLEDGE_BASE_ID", "")
        if kb_id is None
        else kb_id
        ).strip()
        self.region_name = region_name or env("AWS_REGION", "ap-south-1")
        
        # Configure HYBRID vs SEMANTIC according to the selected KB vector-store capabilities
        raw_search_type = (search_type or env("BEDROCK_KB_SEARCH_TYPE", "HYBRID")).strip().upper()
        if raw_search_type not in VALID_SEARCH_TYPES:
            logger.warning(
                "Invalid BEDROCK_KB_SEARCH_TYPE '%s'. Defaulting to 'HYBRID'. Valid options: %s",
                raw_search_type,
                VALID_SEARCH_TYPES,
            )
            raw_search_type = "HYBRID"
        self.search_type = raw_search_type

        self._client = None

    def is_configured(self) -> bool:
        """Returns True if a valid Knowledge Base ID is configured."""
        return bool(self.kb_id and self.kb_id not in PLACEHOLDER_IDS)

    def _get_client(self):
        """Initializes Bedrock Agent Runtime client using EC2 IAM instance credentials."""
        if self._client is not None:
            return self._client

        session_kwargs = {"region_name": self.region_name}
        profile = env("AWS_PROFILE", "").strip()
        if profile and profile not in ("your-aws-profile-name", "realestate-demo"):
            session_kwargs["profile_name"] = profile

        session = boto3.Session(**session_kwargs)
        self._client = session.client("bedrock-agent-runtime", config=KB_CLIENT_CONFIG)
        return self._client

    def retrieve(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """
        Executes document retrieval against Amazon Bedrock Knowledge Bases using bedrock-agent-runtime.
        
        Args:
            query: User's architectural, specification, or general query text.
            top_k: Maximum number of relevant document passages to return.
            
        Returns:
            List of normalized chunk dictionaries:
            [{
                "chunk_id": str,
                "text": str,
                "source": str,
                "page": int,
                "score": float,
                "s3_uri": str,
            }]
            
        Raises:
            BedrockKnowledgeBaseError: If KB is configured but the API call fails.
        """
        cleaned_query = query.strip()
        if not cleaned_query:
            return []

        if not self.is_configured():
            logger.debug("Bedrock Knowledge Base ID is not configured.")
            return []

        client = self._get_client()

        retrieval_config: dict[str, Any] = {
            "vectorSearchConfiguration": {
                "numberOfResults": top_k,
                "overrideSearchType": self.search_type,
            }
        }

        try:
            logger.info(
                "Querying Bedrock Knowledge Base '%s' (SearchType: %s, top_k: %d) for query: '%s'",
                self.kb_id,
                self.search_type,
                top_k,
                cleaned_query[:60],
            )
            response = client.retrieve(
                knowledgeBaseId=self.kb_id,
                retrievalQuery={"text": cleaned_query},
                retrievalConfiguration=retrieval_config,
            )

            raw_results = response.get("retrievalResults", [])
            logger.info("Bedrock Knowledge Base returned %d raw passage(s)", len(raw_results))

            normalized: list[dict[str, Any]] = []
            for idx, item in enumerate(raw_results, 1):
                content = item.get("content", {}).get("text", "").strip()
                if not content:
                    continue

                location = item.get("location", {})
                s3_uri = ""
                source_name = f"KnowledgeBase_Document_{idx}"

                if "s3Location" in location:
                    s3_uri = location["s3Location"].get("uri", "")
                    if s3_uri:
                        parsed = urlparse(s3_uri)
                        # Extract the key or basename
                        source_name = parsed.path.lstrip("/") or Path(s3_uri).name

                score = item.get("score", 0.0)
                metadata = item.get("metadata", {})

                # Extract page if available from metadata attributes
                page_num = 1
                for page_key in ("pageNumber", "page", "page_number", "x-amz-bedrock-kb-document-page-number"):
                    if page_key in metadata:
                        try:
                            page_num = int(metadata[page_key])
                            break
                        except (ValueError, TypeError):
                            pass

                normalized.append({
                    "chunk_id": f"kb_{self.kb_id[:8]}_{idx}",
                    "text": content,
                    "source": source_name,
                    "page": page_num,
                    "score": float(score) if score is not None else 0.0,
                    "s3_uri": s3_uri,
                    "metadata": metadata,
                })

            return normalized

        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "Unknown")
            error_msg = exc.response.get("Error", {}).get("Message", str(exc))
            logger.error("Bedrock Knowledge Base ClientError [%s]: %s", error_code, error_msg)
            raise BedrockKnowledgeBaseError(f"Bedrock Knowledge Base query failed ({error_code}): {error_msg}") from exc

        except (EndpointConnectionError, ConnectTimeoutError) as exc:
            logger.error("Bedrock Knowledge Base connection failure: %s", exc)
            raise BedrockKnowledgeBaseError(f"Cannot reach Bedrock Knowledge Base endpoint: {exc}") from exc

        except Exception as exc:
            logger.error("Unexpected error querying Bedrock Knowledge Base: %s", exc)
            raise BedrockKnowledgeBaseError(f"Unexpected error querying Bedrock Knowledge Base: {exc}") from exc
