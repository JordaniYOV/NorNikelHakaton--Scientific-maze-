from typing import Any
from datetime import datetime
from pydantic import BaseModel, Field
from uuid import UUID
from enum import Enum


# === Enums ===
class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    ENTITIES_EXTRACTED = "entities_extracted"
    RELATIONS_EXTRACTED = "relations_extracted"
    INDEXING = "indexing"
    READY = "ready"
    ERROR = "error"


class EntityType(str, Enum):
    MATERIAL = "Material"
    PROCESS = "Process"
    EQUIPMENT = "Equipment"
    PROPERTY = "Property"
    PARAMETER = "Parameter"
    CONDITION = "Condition"
    EXPERT = "Expert"
    ORGANIZATION = "Organization"
    PUBLICATION = "Publication"
    UNKNOWN = "Unknown"


# === Document ===
class DocumentUploadResponse(BaseModel):
    doc_id: UUID
    status: DocumentStatus
    message: str


class DocumentStatusResponse(BaseModel):
    id: UUID
    filename: str
    status: DocumentStatus
    uploaded_at: datetime
    updated_at: datetime
    error_message: str | None = None


class DocumentListResponse(BaseModel):
    total: int
    items: list[DocumentStatusResponse]


# === Chunk ===
class ChunkResponse(BaseModel):
    id: UUID
    chunk_index: int
    text: str
    start_pos: int | None = None
    end_pos: int | None = None


# === Entity ===
class EntityCreate(BaseModel):
    name: str
    canonical_name: str
    type: EntityType
    confidence: float = Field(ge=0, le=1)
    context: str | None = None


class EntityResponse(BaseModel):
    id: UUID
    name: str
    canonical_name: str
    type: EntityType
    confidence: float
    context: str | None = None
    extracted_at: datetime
    verified: bool


# === Relation ===
class RelationCreate(BaseModel):
    source_name: str
    target_name: str
    relation_type: str
    confidence: float = Field(ge=0, le=1)
    context: str | None = None


class RelationResponse(BaseModel):
    id: UUID
    source_entity: EntityResponse
    target_entity: EntityResponse
    relation_type: str
    confidence: float
    context: str | None
    extracted_at: datetime


# === Search ===
class SearchRequest(BaseModel):
    query: str
    filters: dict[str, Any] | None = None
    top_k: int = Field(default=10, ge=1, le=50)


class SearchResult(BaseModel):
    text: str
    doc_id: UUID
    chunk_index: int
    score: float
    entities: list[dict[str, Any]] = []
    metadata: dict[str, Any] = {}


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    total_found: int


# === Graph ===
class GraphNode(BaseModel):
    id: str
    name: str
    canonical_name: str
    type: str
    properties: dict[str, Any] = {}


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str
    properties: dict[str, Any] = {}


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class GraphQueryRequest(BaseModel):
    cypher: str
    parameters: dict[str, Any] = None


# === Answer ===
class AnswerRequest(BaseModel):
    query: str
    include_sources: bool = True
    include_graph: bool = True


class SourceCitation(BaseModel):
    doc_id: UUID
    filename: str
    chunk_index: int
    text: str
    confidence: float


class AnswerResponse(BaseModel):
    answer: str
    sources: list[SourceCitation]
    related_entities: list[dict[str, Any]] = []
    gaps: list[str] = []
    graph: GraphResponse | None = None