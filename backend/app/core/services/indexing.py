import uuid
from typing import  Any
from qdrant_client.models import PointStruct, Distance, VectorParams
from sentence_transformers import SentenceTransformer
from app.core.config import settings
from app.db.database import qdrant_client


class IndexingService:
    """Индексация чанков в векторное хранилище"""
    
    def __init__(self):
        self.collection_name = settings.QDRANT_COLLECTION
        self.model = None
        self._init_model()
        self._ensure_collection()
    
    def _init_model(self):
        """Инициализация модели эмбеддингов"""
        try:
            # BGE-M3 — мультиязычная, поддерживает русский
            self.model = SentenceTransformer('BAAI/bge-m3')
            print("Модель BGE-M3 загружена")
        except Exception as e:
            print(f"Ошибка загрузки BGE-M3: {e}")
            # Fallback на более лёгкую модель
            self.model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
            print("Используется fallback модель")
    
    def _ensure_collection(self):
        """Убедиться, что коллекция существует"""
        try:
            collections = qdrant_client.get_collections().collections
            collection_names = [c.name for c in collections]
            
            if self.collection_name not in collection_names:
                qdrant_client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
                )
                print(f"Коллекция {self.collection_name} создана")
        except Exception as e:
            print(f"Ошибка проверки коллекции: {e}")
    
    def get_embedding(self, text: str) -> list[float]:
        """Получить векторное представление текста"""
        if self.model is None:
            raise RuntimeError("Модель эмбеддингов не инициализирована")
        
        # BGE-M3 рекомендует префикс для retrieval
        instruction = "Represent this sentence for searching relevant passages: "
        embedding = self.model.encode(instruction + text, normalize_embeddings=True)
        return embedding.tolist()
    
    def index_chunks(self, doc_id: str, chunks: list[dict[str, Any]]) -> list[str]:
        """
        Индексировать список чанков.
        chunks: [{"chunk_id": str, "chunk_index": int, "text": str, "entities": [...]}]
        Возвращает список vector_id
        """
        points = []
        vector_ids = []
        
        for chunk in chunks:
            chunk_id = chunk.get("chunk_id", str(uuid.uuid4()))
            text = chunk["text"]
            
            # Получаем эмбеддинг
            vector = self.get_embedding(text)
            
            # Формируем payload
            payload = {
                "text": text,
                "doc_id": str(doc_id),
                "chunk_id": chunk_id,
                "chunk_index": chunk.get("chunk_index", 0),
                "entities": chunk.get("entities", []),
                "metadata": {
                    "source": chunk.get("source", "unknown")
                }
            }
            
            point = PointStruct(
                id=chunk_id,
                vector=vector,
                payload=payload
            )
            points.append(point)
            vector_ids.append(chunk_id)
        
        # Загружаем пакетом
        if points:
            qdrant_client.upsert(
                collection_name=self.collection_name,
                points=points
            )
        
        return vector_ids
    
    def search(self, query: str, top_k: int = 10, filters: dict[str, Any] = None) -> list[dict[str, Any]]:
        """Семантический поиск по запросу"""
        query_vector = self.get_embedding(query)
        
        search_params = {
            "collection_name": self.collection_name,
            "query_vector": query_vector,
            "limit": top_k,
            "with_payload": True,
        }
        
        if filters:
            search_params["query_filter"] = filters
        
        results = qdrant_client.search(**search_params)
        
        return [
            {
                "id": str(r.id),
                "score": r.score,
                "text": r.payload.get("text", ""),
                "doc_id": r.payload.get("doc_id", ""),
                "chunk_index": r.payload.get("chunk_index", 0),
                "entities": r.payload.get("entities", []),
                "metadata": r.payload.get("metadata", {})
            }
            for r in results
        ]
    
    def delete_by_doc_id(self, doc_id: str):
        """Удалить все чанки документа"""
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        
        qdrant_client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="doc_id",
                        match=MatchValue(value=doc_id)
                    )
                ]
            )
        )



indexing_service = IndexingService()