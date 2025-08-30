from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from uuid import uuid4
from pydantic import BaseModel, Field


class DocumentSection(str, Enum):
    PRODUCT = "product"
    POLICY = "policy"
    FAQ = "faq"
    REVIEW = "review"
    OTHER = "other"


class Document(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    shop_id: str
    url: str
    title: str
    section: DocumentSection
    text: str
    lang: str = "en"
    ts_fetched: datetime
    meta: Dict[str, Any] = Field(default_factory=dict)


class Chunk(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    doc_id: str
    vector: List[float]
    text: str
    start_char: int
    end_char: int


class ConversationTurn(BaseModel):
    role: str
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    sources: Optional[List[Dict[str, Any]]] = None


class Conversation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    shop_id: str
    turns: List[ConversationTurn] = Field(default_factory=list)
    summary: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ToolTrace(BaseModel):
    ts: datetime = Field(default_factory=datetime.utcnow)
    name: str
    input: Dict[str, Any]
    output: Dict[str, Any]
    latency_ms: int


class CrawlRequest(BaseModel):
    shop_id: str
    shop_url: str
    include: List[str] = Field(default_factory=list)
    exclude: List[str] = Field(default_factory=list)


class CrawlStatus(BaseModel):
    shop_id: str
    status: str
    pages_discovered: int
    pages_processed: int
    pages_indexed: int
    last_error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class RAGQuery(BaseModel):
    shop_id: str
    question: str
    top_k: int = 18
    rerank_top_n: int = 8


class Source(BaseModel):
    url: str
    title: str
    snippet: str
    score: float


class RAGResponse(BaseModel):
    answer: str
    sources: List[Source]
    tool_traces: List[ToolTrace] = Field(default_factory=list)


class ShopInfo(BaseModel):
    shop_id: str
    name: str
    url: str
    status: str
    last_crawled: Optional[datetime] = None
    document_count: int = 0
    chunk_count: int = 0