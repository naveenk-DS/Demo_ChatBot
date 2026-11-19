from typing import Literal, Optional
from pydantic import BaseModel, Field

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[ChatMessage] = Field(default_factory=list)
    provider: Literal["openai", "gemini", "ollama"] = "gemini"

class SearchFilters(BaseModel):
    intent: Literal["property_search", "general_question", "contact_request"] = "property_search"
    location: Optional[str] = Field(default=None, max_length=100)
    city: Optional[str] = Field(default=None, max_length=100)
    bhk: Optional[int] = Field(default=None, ge=1, le=10)
    min_price: Optional[int] = Field(default=None, ge=0)
    max_price: Optional[int] = Field(default=None, ge=0)
    property_type: Optional[str] = Field(default=None, max_length=80)
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    assistant_message: Optional[str] = ""

class EnquiryRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=7, max_length=30)
    property_id: Optional[str] = Field(default=None, max_length=100)
    message: str = Field(min_length=3, max_length=2000)
    consent: bool
