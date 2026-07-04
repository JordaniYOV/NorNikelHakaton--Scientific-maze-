"""Celery задачи для обработки документов"""
import asyncio
from uuid import UUID
from celery import shared_task
from sqlalchemy import select

from ..db.database import SessionLocal
from ..core.models import Document, DocumentStatus, Chunk, Relation, Entity
from ..core.services.document import document_service
from ..core.services.parser import ParserService
from ..core.services.extraction import extraction_service
from ..core.services.indexing import indexing_service
from ..core.services.graph import graph_service
from ..utils.chunker import chunk_document


@shared_task(bind=True, max_retries=3)
def process_document(self, doc_id: str):
    """
    Полный пайплайн обработки документа:
    parse -> extract_entities -> extract_relations -> index_vectors -> build_graph
    """
    db = SessionLocal()
    try:
        state = select(Document).filter(Document.id == UUID(doc_id))
        doc_obj = db.execute(state)
        doc = doc_obj.scalar_one_or_none()
        if not doc:
            raise ValueError(f"Документ {doc_id} не найден")
        
        # Шаг 1: Парсинг
        document_service.update_status(db, UUID(doc_id), DocumentStatus.PARSING)
        parsed_text = ParserService.parse_file(doc.storage_path)
        doc.parsed_text = parsed_text
        print(doc)
        # Шаг 2: Разбиение на чанки
        chunks_data = chunk_document(parsed_text)
        chunk_records = []
        for start, end, text in chunks_data:
            chunk = Chunk(
                doc_id=UUID(doc_id),
                chunk_index=len(chunk_records),
                text=text,
                start_pos=start,
                end_pos=end
            )
            print(f"Добавляем чанк {chunk.chunk_index} для документа {doc_id}: {len(text)} символов")
            db.add(chunk)
            chunk_records.append(chunk)
        print(f"Добавлено {len(chunk_records)} чанков для документа {doc_id}")
        db.commit()
        
        # Обновляем ID чанков после commit
        for chunk in chunk_records:
            db.refresh(chunk)
        
        # Шаг 3: Извлечение сущностей
        document_service.update_status(db, UUID(doc_id), DocumentStatus.ENTITIES_EXTRACTED)
        all_entities = []
        
        for chunk in chunk_records:
            
            entities = extraction_service.extract_entities(chunk.text)
            
            # Сохраняем в БД
            for ent in entities:
                entity = Entity(
                    doc_id=UUID(doc_id),
                    chunk_id=chunk.id,
                    name=ent["name"],
                    canonical_name=ent.get("canonical_name", ent["name"]),
                    type=ent.get("type", "Unknown"),
                    confidence=ent.get("confidence", 1.0),
                    context=ent.get("context", "")[:1000]
                )
                print(f"Добавляем сущность '{entity.name}' для документа {doc_id}, чанк {chunk.chunk_index}")
                db.add(entity)
                all_entities.append({
                    "id": str(entity.id),
                    "name": ent["name"],
                    "canonical_name": ent.get("canonical_name", ent["name"]),
                    "type": ent.get("type", "Unknown"),
                    "confidence": ent.get("confidence", 1.0),
                    "context": ent.get("context", "")
                })
            print(f"Извлечено {len(entities)} сущностей из чанка {chunk.chunk_index} документа {doc_id}")
            db.commit()
        
        # Шаг 4: Извлечение связей
        document_service.update_status(db, UUID(doc_id), DocumentStatus.RELATIONS_EXTRACTED)
        all_relations = []
        
        for chunk in chunk_records:
            chunk_entities = [e for e in all_entities if str(chunk.id) in [str(ce.chunk_id) for ce in db.query(Entity).filter(Entity.chunk_id == chunk.id).all()]]
            print(f"Извлекаем связи из чанка {chunk.chunk_index} документа {doc_id}, найдено {len(chunk_entities)} сущностей")
            if len(chunk_entities) >= 2:
                relations = extraction_service.extract_relations(chunk.text, chunk_entities)
                
                for rel in relations:
                    
                    # Находим ID сущностей
                    source = db.query(Entity).filter(
                        Entity.doc_id == UUID(doc_id),
                        Entity.name == rel["source"]
                    ).first()
                    target = db.query(Entity).filter(
                        Entity.doc_id == UUID(doc_id),
                        Entity.name == rel["target"]
                    ).first()
                    
                    if source and target:
                        relation = Relation(
                            source_entity_id=source.id,
                            target_entity_id=target.id,
                            relation_type=rel.get("relation_type", "RELATED_TO"),
                            confidence=rel.get("confidence", 1.0),
                            context=rel.get("context", "")[:1000],
                            doc_id=UUID(doc_id),
                            chunk_id=chunk.id
                        )
                        db.add(relation)
                        all_relations.append({
                            "source": rel["source"],
                            "target": rel["target"],
                            "relation_type": rel.get("relation_type", "RELATED_TO"),
                            "confidence": rel.get("confidence", 1.0),
                            "context": rel.get("context", "")
                        })
                    print(f"Добавляем связь '{rel['source']}' -> '{rel['target']}' для документа {doc_id}, чанк {chunk.chunk_index}")
                db.commit()
        
        # Шаг 5: Индексация векторов
        document_service.update_status(db, UUID(doc_id), DocumentStatus.INDEXING)
        
        chunks_for_index = []
        for chunk in chunk_records:
            chunk_entities = db.query(Entity).filter(Entity.chunk_id == chunk.id).all()
            chunks_for_index.append({
                "chunk_id": str(chunk.id),
                "chunk_index": chunk.chunk_index,
                "text": chunk.text,
                "entities": [
                    {"name": e.name, "type": e.type, "canonical_name": e.canonical_name}
                    for e in chunk_entities
                ],
                "source": doc.filename
            })
        
        indexing_service.index_chunks(doc_id, chunks_for_index)
        
        # Шаг 6: Построение графа
        graph_service.build_from_document(doc_id, all_entities, all_relations)
        graph_service.create_document_node(doc_id, doc.filename, doc.file_type)
        
        # Финальный статус
        document_service.update_status(db, UUID(doc_id), DocumentStatus.READY)
        
        return {"status": "success", "doc_id": doc_id, "chunks": len(chunk_records),
                "entities": len(all_entities), "relations": len(all_relations)}
        
    except Exception as exc:
        document_service.update_status(db, UUID(doc_id), DocumentStatus.ERROR, str(exc))
        # Повторная попытка
        raise self.retry(exc=exc, countdown=60)
        
    finally:
        db.close()


@shared_task
def delete_document_task(doc_id: str):
    """Асинхронное удаление документа"""
    db = SessionLocal()
    try:
        document_service.delete_document(db, UUID(doc_id))
        return {"status": "deleted", "doc_id": doc_id}
    finally:
        db.close()