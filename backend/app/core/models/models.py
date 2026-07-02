import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Float, Integer, Boolean, ForeignKey, ARRAY, JSON, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
import enum

Base = declarative_base()

class DocumentStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    ENTITIES_EXTRACTED = "entities_extracted"
    RELATIONS_EXTRACTED = "relations_extracted"
    INDEXING = "indexing"
    READY = "ready"
    ERROR = "error"


class TaskType(str, enum.Enum):
    PARSE = "parse"
    EXTRACT_ENTITIES = "extract_entities"
    EXTRACT_RELATIONS = "extract_relations"
    INDEX_VECTORS = "index_vectors"
    BUILD_GRAPH = "build_graph"


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class EntityType(str, enum.Enum):
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


class Document(Base):
    __tablename__ = "documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(500), nullable=False)
    storage_path = Column(String(1000), nullable=False)
    file_type = Column(String(50), nullable=False)
    status = Column(Enum(DocumentStatus), default=DocumentStatus.UPLOADED)
    parsed_text = Column(Text)
    error_message = Column(Text)
    uploaded_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")
    entities = relationship("Entity", back_populates="document", cascade="all, delete-orphan")
    relations = relationship("Relation", back_populates="document", cascade="all, delete-orphan")
    tasks = relationship("ProcessingTask", back_populates="document", cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "chunks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doc_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    start_pos = Column(Integer)
    end_pos = Column(Integer)
    vector_id = Column(String(100))
    
    document = relationship("Document", back_populates="chunks")
    entities = relationship("Entity", back_populates="chunk")
    relations = relationship("Relation", back_populates="chunk")


class Entity(Base):
    __tablename__ = "entities"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doc_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    chunk_id = Column(UUID(as_uuid=True), ForeignKey("chunks.id"))
    name = Column(String(500), nullable=False)
    canonical_name = Column(String(500), nullable=False)
    type = Column(Enum(EntityType), nullable=False)
    confidence = Column(Float, default=1.0)
    context = Column(Text)
    extracted_at = Column(DateTime, default=datetime.utcnow)
    verified = Column(Boolean, default=False)
    
    document = relationship("Document", back_populates="entities")
    chunk = relationship("Chunk", back_populates="entities")
    source_relations = relationship("Relation", foreign_keys="Relation.source_entity_id", back_populates="source_entity")
    target_relations = relationship("Relation", foreign_keys="Relation.target_entity_id", back_populates="target_entity")


class Relation(Base):
    __tablename__ = "relations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False)
    target_entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False)
    relation_type = Column(String(100), nullable=False)
    confidence = Column(Float, default=1.0)
    context = Column(Text)
    doc_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    chunk_id = Column(UUID(as_uuid=True), ForeignKey("chunks.id"))
    extracted_at = Column(DateTime, default=datetime.now)
    
    source_entity = relationship("Entity", foreign_keys=[source_entity_id], back_populates="source_relations")
    target_entity = relationship("Entity", foreign_keys=[target_entity_id], back_populates="target_relations")
    document = relationship("Document", back_populates="relations")
    chunk = relationship("Chunk", back_populates="relations")


class ProcessingTask(Base):
    __tablename__ = "processing_tasks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doc_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    task_type = Column(Enum(TaskType), nullable=False)
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    error_message = Column(Text)
    
    document = relationship("Document", back_populates="tasks")


class SynonymDictionary(Base):
    __tablename__ = "synonym_dictionary"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    canonical_name = Column(String(500), nullable=False)
    synonyms = Column(ARRAY(String), default=[])
    type = Column(String(100))