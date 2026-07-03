"""Сервис управления документами"""
import os

from uuid import UUID
from sqlalchemy.orm import Session
from app.core.models import Document, DocumentStatus, Chunk, Entity, Relation, ProcessingTask, TaskStatus
from app.core.schemas import DocumentStatusResponse, DocumentListResponse


class DocumentService:
    """CRUD операции с документами и их статусами"""
    
    @staticmethod
    def create_document(db: Session, filename: str, storage_path: str, file_type: str) -> Document:
        """Создать запись о документе"""
        doc = Document(
            filename=filename,
            storage_path=storage_path,
            file_type=file_type,
            status=DocumentStatus.UPLOADED
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return doc
    
    @staticmethod
    def get_document(db: Session, doc_id: UUID) -> Optional[Document]:
        """Получить документ по ID"""
        return db.query(Document).filter(Document.id == doc_id).first()
    
    @staticmethod
    def list_documents(db: Session, status: Optional[DocumentStatus] = None,
                       skip: int = 0, limit: int = 100) -> DocumentListResponse:
        """Список документов с фильтрацией"""
        query = db.query(Document)
        if status:
            query = query.filter(Document.status == status)
        
        total = query.count()
        items = query.order_by(Document.uploaded_at.desc()).offset(skip).limit(limit).all()
        
        return DocumentListResponse(
            total=total,
            items=[
                DocumentStatusResponse(
                    id=item.id,
                    filename=item.filename,
                    status=item.status,
                    uploaded_at=item.uploaded_at,
                    updated_at=item.updated_at,
                    error_message=item.error_message
                )
                for item in items
            ]
        )
    
    @staticmethod
    def update_status(db: Session, doc_id: UUID, status: DocumentStatus,
                      error_message: Optional[str] = None):
        """Обновить статус документа"""
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            doc.status = status
            if error_message:
                doc.error_message = error_message
            db.commit()
            db.refresh(doc)
        return doc
    
    @staticmethod
    def delete_document(db: Session, doc_id: UUID):
        """Полное удаление документа со всеми данными"""
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            return False
        
        # 1. Удалить файл
        if os.path.exists(doc.storage_path):
            os.remove(doc.storage_path)
        
        # 2. Удалить из Qdrant
        from app.core.services.indexing import indexing_service
        indexing_service.delete_by_doc_id(str(doc_id))
        
        # 3. Удалить из Neo4j
        from app.core.services.graph import graph_service
        graph_service.delete_document(str(doc_id))
        
        # 4. Удалить из PostgreSQL (каскадно удалит chunks, entities, relations, tasks)
        db.delete(doc)
        db.commit()
        
        return True
    
    @staticmethod
    def create_task(db: Session, doc_id: UUID, task_type: str) -> ProcessingTask:
        """Создать задачу обработки"""
        task = ProcessingTask(
            doc_id=doc_id,
            task_type=task_type,
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task



document_service = DocumentService()