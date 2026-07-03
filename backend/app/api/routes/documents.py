"""API endpoints для работы с документами"""
from uuid import UUID
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core.models import DocumentStatus
from app.core.schemas import DocumentUploadResponse, DocumentStatusResponse, DocumentListResponse
from app.core.services.document import document_service
from app.core.services.parser import ParserService
from app.tasks.document_tasks import process_document, delete_document_task


router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Загрузить документ и запустить обработку"""
    # Проверка формата
    import os
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ParserService.SUPPORTED_TYPES:
        raise HTTPException(400, f"Неподдерживаемый формат: {ext}")
    
    # Сохраняем файл
    content = await file.read()
    file_path = ParserService.save_upload(content, file.filename)
    
    # Создаём запись в БД
    doc = document_service.create_document(db, file.filename, file_path, ext)
    
    # Запускаем обработку в фоне
    process_document.delay(str(doc.id))
    
    return DocumentUploadResponse(
        doc_id=doc.id,
        status=doc.status,
        message="Документ загружен и поставлен в очередь обработки"
    )


@router.get("/{doc_id}", response_model=DocumentStatusResponse)
def get_document_status(doc_id: UUID, db: Session = Depends(get_db)):
    """Получить статус документа"""
    doc = document_service.get_document(db, doc_id)
    if not doc:
        raise HTTPException(404, "Документ не найден")
    
    return DocumentStatusResponse(
        id=doc.id,
        filename=doc.filename,
        status=doc.status,
        uploaded_at=doc.uploaded_at,
        updated_at=doc.updated_at,
        error_message=doc.error_message
    )


@router.get("/", response_model=DocumentListResponse)
def list_documents(
    status: str = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Список документов"""
    status_enum = DocumentStatus(status) if status else None
    return document_service.list_documents(db, status_enum, skip, limit)


@router.delete("/{doc_id}")
def delete_document(doc_id: UUID, db: Session = Depends(get_db)):
    """Удалить документ со всеми данными"""
    doc = document_service.get_document(db, doc_id)
    if not doc:
        raise HTTPException(404, "Документ не найден")
    
    delete_document_task.delay(str(doc_id))
    return {"message": "Удаление поставлено в очередь", "doc_id": doc_id}