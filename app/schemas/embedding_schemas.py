from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, HttpUrl


class KnowledgeBaseCreateInput(BaseModel):
    name: Optional[str] = Field(None, description="Human-friendly name for the PDF knowledge base")
    source_url: HttpUrl = Field(..., description="Public PDF URL to ingest")
    chunk_size: int = Field(1000, ge=200, le=4000, description="Chunk size in characters")
    chunk_overlap: int = Field(200, ge=0, le=1000, description="Overlap in characters between chunks")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional extra metadata")


class KnowledgeBaseUpdateInput(BaseModel):
    name: Optional[str] = Field(None, description="Update the name")
    source_url: Optional[HttpUrl] = Field(None, description="Replace the source PDF URL")
    chunk_size: Optional[int] = Field(None, ge=200, le=4000, description="Chunk size in characters")
    chunk_overlap: Optional[int] = Field(None, ge=0, le=1000, description="Overlap in characters between chunks")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Replace metadata")
    regenerate: bool = Field(True, description="Rebuild embeddings when updating")


class KnowledgeBaseData(BaseModel):
    kb_id: str
    name: Optional[str]
    source_url: str
    status: str
    chunk_count: int
    embedding_model: Optional[str]
    created_at: datetime
    updated_at: datetime
    metadata: Optional[Dict[str, Any]] = None
    last_error: Optional[str] = None


class KnowledgeBaseResponse(BaseModel):
    success: bool
    message: str
    data: Optional[KnowledgeBaseData] = None


class KnowledgeBaseListResponse(BaseModel):
    success: bool
    total: int
    data: List[KnowledgeBaseData]
