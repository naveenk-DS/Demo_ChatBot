from typing import Any, Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


UNSPECIFIED_SENTINELS = {
    "",
    "null",
    "none",
    "not specified",
    "unspecified",
    "not mentioned",
    "n/a",
    "na",
    "any",
    "unknown",
    "all",
    "-",
    "nil",
    "undefined",
}


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class SearchFilters(BaseModel):
    intent: Literal["property_search", "document_qa", "media_request", "general_question", "contact_request", "search_refinement"] = "property_search"
    location: Optional[str] = Field(default=None, max_length=100)
    city: Optional[str] = Field(default=None, max_length=100)
    bhk: Optional[int] = Field(default=None, ge=1, le=10)
    min_price: Optional[int] = Field(default=None, ge=0)
    max_price: Optional[int] = Field(default=None, ge=0)
    property_type: Optional[str] = Field(default=None, max_length=80)
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    assistant_message: Optional[str] = ""

    @field_validator("bhk", "min_price", "max_price", mode="before")
    @classmethod
    def clean_numeric_filters(cls, v: Any) -> Optional[int]:
        """Converts empty/unspecified strings to None and parses numeric string values to integers."""
        if v is None:
            return None
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped or stripped.lower() in UNSPECIFIED_SENTINELS:
                return None
            try:
                return int(stripped)
            except ValueError:
                raise ValueError("Input should be a valid integer, unable to parse string as an integer")
        return v

    @field_validator("location", "city", "property_type", mode="before")
    @classmethod
    def clean_string_filters(cls, v: Any) -> Optional[str]:
        """Converts empty or unspecified string filters to None."""
        if v is None:
            return None
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped or stripped.lower() in UNSPECIFIED_SENTINELS:
                return None
            return stripped
        return v

    @model_validator(mode="after")
    def validate_price_bounds(self) -> "SearchFilters":
        """Ensures min_price does not exceed max_price when both are set."""
        if self.min_price is not None and self.max_price is not None and self.min_price > self.max_price:
            raise ValueError("Minimum price cannot exceed maximum price.")
        return self


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[ChatMessage] = Field(default_factory=list)
    provider: Literal["openai", "gemini", "ollama"] = "gemini"
    filters: Optional[SearchFilters] = None


class EnquiryRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=7, max_length=30)
    property_id: Optional[str] = Field(default=None, max_length=100)
    message: str = Field(min_length=3, max_length=2000)
    consent: bool
