"""Сервис поиска: гибридный векторный + графовый"""
from typing import Any
from ...core.services.indexing import indexing_service
from ...core.services.graph import graph_service



class SearchService:
    """Гибридный поиск по корпусу документов"""
    
    def search(self, query: str, top_k: int = 10,
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
                entity_name = entity.get("name", "")
                if not entity_name:
                    continue
                neighbors = graph_service.get_neighbors(entity_name, depth=2)
                for node in neighbors.get("nodes", []):
                    if node["name"] == entity_name:
                        continue
                    related_chunks = self._find_chunks_for_entity(node["name"])
                    for chunk in related_chunks:
                        graph_results.append({
                            "type": "graph",
                            "text": chunk["text"],
                            "doc_id": chunk["doc_id"],
                            "chunk_index": chunk["chunk_index"],
                            "score": 0.75,
                            "entities": [node],
                            "path": f"{entity_name} → {node['name']}",
                            "source": "graph"
                        })
        
        # 4. Объединение: векторные результаты приоритетны
        seen_docs = set()
        combined = []
        
        for r in sorted(vector_results + graph_results, key=lambda x: x.get("score", 0), reverse=True):
            doc_id = r.get("doc_id")
            if doc_id not in seen_docs:
                combined.append(r)
                seen_docs.add(doc_id)
            
            if len(combined) >= top_k:
                break
        
        return {
            "query": query,
            "results": combined,
            "total_found": len(vector_results) + len(graph_results),
            "query_entities": [e["name"] for e in query_entities]
        }
    
    def _extract_query_entities(self, query: str) -> list[dict[str, str]]:
        """Простое извлечение сущностей из запроса (для MVP)"""
        from ...utils.synonymus import SYNONYMS
        
        found = []
        query_lower = query.lower()
        
        for etype, entries in SYNONYMS.items():
            for canonical, synonyms in entries.items():
                all_forms = [canonical] + synonyms
                for form in all_forms:
                    if form.lower() in query_lower:
                        found.append({
                            "name": canonical,
                            "type": etype
                        })
                        break
        
        return list({frozenset(d.items()): d for d in found}.values())
    
    def _find_chunks_for_entity(self, entity_name: str) -> list[dict]:
        """Найти чанки, содержащие сущность"""
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
        """Получить граф сущностей для документа"""
        return graph_service.get_neighbors(doc_id, depth=1)

search_service = SearchService()