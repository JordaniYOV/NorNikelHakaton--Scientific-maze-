"""Сервис поиска: гибридный векторный + графовый"""
from typing import Any
from app.core.services.indexing import indexing_service
from app.core.services.graph import graph_service
from app.db.database import neo4j_conn


class SearchService:
    """Гибридный поиск по корпусу документов"""
    
    async def search(self, query: str, top_k: int = 10,
                     filters: dict[str, Any] = None) -> dict[str, Any]:
        """
        Гибридный поиск:
        1. Векторный поиск в Qdrant
        2. Графовый поиск по сущностям
        3. Объединение и реранкинг
        """
        # 1. Векторный поиск
        vector_results = indexing_service.search(query, top_k=top_k * 2)
        
        # 2. Извлечение сущностей из запроса (простая эвристика)
        query_entities = self._extract_query_entities(query)
        
        # 3. Графовый поиск по сущностям
        graph_results = []
        if query_entities:
            for entity in query_entities:
                neighbors = graph_service.get_neighbors(entity, depth=2)
                # Преобразуем в формат результатов
                for node in neighbors.get("nodes", []):
                    if node["name"] != entity:
                        graph_results.append({
                            "entity": node,
                            "source": "graph",
                            "score": 0.8  # Базовый скор для графовых результатов
                        })
        
        # 4. Объединение: векторные результаты приоритетны
        seen_docs = set()
        combined = []
        
        # Сначала векторные с высоким скором
        for r in vector_results:
            if r["doc_id"] not in seen_docs and r["score"] > 0.5:
                combined.append({
                    "type": "vector",
                    "text": r["text"],
                    "doc_id": r["doc_id"],
                    "chunk_index": r["chunk_index"],
                    "score": r["score"],
                    "entities": r.get("entities", [])
                })
                seen_docs.add(r["doc_id"])
        
        # Добавляем графовые, если есть новые сущности
        for gr in graph_results:
            # Проверяем, есть ли связанные чанки
            related_chunks = self._find_chunks_for_entity(gr["entity"]["name"])
            for chunk in related_chunks:
                if chunk["doc_id"] not in seen_docs:
                    combined.append({
                        "type": "graph",
                        "text": chunk["text"],
                        "doc_id": chunk["doc_id"],
                        "chunk_index": chunk["chunk_index"],
                        "score": gr["score"] * 0.7,  # Небольшой штраф
                        "entities": [gr["entity"]],
                        "path": f"{entity} -> {gr['entity']['name']}"
                    })
                    seen_docs.add(chunk["doc_id"])
        
        # Сортируем по скору и обрезаем
        combined.sort(key=lambda x: x["score"], reverse=True)
        
        return {
            "query": query,
            "results": combined[:top_k],
            "total_found": len(combined),
            "query_entities": query_entities
        }
    
    def _extract_query_entities(self, query: str) -> list[str]:
        """Простое извлечение сущностей из запроса (для MVP)"""
        # TODO: заменить на LLM-based извлечение
        from app.utils.synonymus import SYNONYMS
        
        found = []
        query_lower = query.lower()
        
        for etype, entries in SYNONYMS.items():
            for canonical, synonyms in entries.items():
                all_forms = [canonical] + synonyms
                for form in all_forms:
                    if form.lower() in query_lower:
                        found.append(canonical)
                        break
        
        return list(set(found))
    
    def _find_chunks_for_entity(self, entity_name: str) -> list[dict]:
        """Найти чанки, содержащие сущность"""
        # Ищем в Qdrant по фильтру
        # from qdrant_client.models import Filter, FieldCondition, MatchValue
        
        results = indexing_service.search(
            query=entity_name,  # Семантический поиск по названию
            top_k=10
        )
        
        # Фильтруем по наличию сущности в payload
        filtered = []
        for r in results:
            entities = r.get("entities", [])
            for e in entities:
                if e.get("canonical_name") == entity_name or e.get("name") == entity_name:
                    filtered.append(r)
                    break
        
        return filtered
    
    def get_document_graph(self, doc_id: str) -> dict[str, Any]:
        """Получить граф сущностей для конкретного документа"""
        result = neo4j_conn.query("""
            MATCH (d:Document {id: $doc_id})-[:CONTAINS]->(e:Entity)
            OPTIONAL MATCH (e)-[r:RELATION]->(other:Entity)
            WHERE r.doc_id = $doc_id
            RETURN e, collect({target: other, rel: r}) as connections
        """, {"doc_id": doc_id})
        
        nodes = {}
        edges = []
        
        for record in result:
            entity = record["e"]
            nodes[entity["canonical_name"]] = {
                "id": entity.get("id", ""),
                "name": entity["canonical_name"],
                "type": entity["type"]
            }
            
            for conn in record["connections"]:
                if conn["target"] is None:
                    continue
                target = conn["target"]
                rel = conn["rel"]
                
                nodes[target["canonical_name"]] = {
                    "id": target.get("id", ""),
                    "name": target["canonical_name"],
                    "type": target["type"]
                }
                
                edges.append({
                    "source": entity["canonical_name"],
                    "target": target["canonical_name"],
                    "type": rel.get("type", "RELATION"),
                    "properties": {"confidence": rel.get("confidence", 1.0)}
                })
        
        return {
            "nodes": list(nodes.values()),
            "edges": edges
        }

search_service = SearchService()