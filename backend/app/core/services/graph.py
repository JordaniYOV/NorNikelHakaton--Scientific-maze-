"""Сервис работы с графом Neo4j"""
from typing import Any
from ...db.database import neo4j_conn
from ...utils.synonymus import normalize_entity


class GraphService:
    """Управление графом знаний в Neo4j"""
    
    def __init__(self):
        self._init_schema()
    
    def _init_schema(self):
        """Инициализация схемы: индексы и ограничения"""
        # Индексы для быстрого поиска
        neo4j_conn.query("""
            CREATE INDEX entity_name_index IF NOT EXISTS
            FOR (e:Entity) ON (e.canonical_name)
        """)
        neo4j_conn.query("""
            CREATE INDEX entity_type_index IF NOT EXISTS
            FOR (e:Entity) ON (e.type)
        """)
        neo4j_conn.query("""
            CREATE INDEX document_id_index IF NOT EXISTS
            FOR (d:Document) ON (d.id)
        """)
    
    def create_document_node(self, doc_id: str, filename: str, file_type: str):
        """Создать узел документа"""
        neo4j_conn.query("""
            MERGE (d:Document {id: $doc_id})
            SET d.filename = $filename,
                d.file_type = $file_type,
                d.created_at = datetime()
        """, {"doc_id": doc_id, "filename": filename, "file_type": file_type})
    
    def create_entity(self, entity_id: str, name: str, canonical_name: str,
                      entity_type: str, doc_id: str, chunk_id: str | None = None,
                      confidence: float = 1.0, context: str = "") -> str:
        """
        Создать или обновить сущность. Возвращает ID сущности в графе.
        """
        # Нормализация
        canonical = normalize_entity(canonical_name, entity_type)
        
        # MERGE по canonical_name и type — уникальная комбинация
        result = neo4j_conn.query("""
            MERGE (e:Entity {canonical_name: $canonical, type: $etype})
            ON CREATE SET e.id = $eid,
                          e.name = $name,
                          e.first_seen = datetime(),
                          e.confidence = $confidence,
                          e.context = $context
            ON MATCH SET e.name = CASE WHEN $confidence > e.confidence THEN $name ELSE e.name END,
                         e.confidence = CASE WHEN $confidence > e.confidence THEN $confidence ELSE e.confidence END
            WITH e
            MATCH (d:Document {id: $doc_id})
            MERGE (d)-[:CONTAINS]->(e)
            RETURN e.id as entity_id
        """, {
            "eid": entity_id,
            "name": name,
            "canonical": canonical,
            "etype": entity_type,
            "doc_id": doc_id,
            "confidence": confidence,
            "context": context[:500]  # Ограничиваем длину
        })
        
        return result[0]["entity_id"] if result else entity_id
    
    def create_relation(self, source_canonical: str, target_canonical: str,
                        relation_type: str, doc_id: str,
                        confidence: float = 1.0, context: str = ""):
        """Создать связь между сущностями"""
        neo4j_conn.query("""
            MATCH (s:Entity {canonical_name: $source})
            MATCH (t:Entity {canonical_name: $target})
            MERGE (s)-[r:RELATION {type: $rtype, doc_id: $doc_id}]->(t)
            ON CREATE SET r.confidence = $confidence,
                          r.context = $context,
                          r.created_at = datetime()
            ON MATCH SET r.confidence = CASE WHEN $confidence > r.confidence 
                                             THEN $confidence ELSE r.confidence END
        """, {
            "source": source_canonical,
            "target": target_canonical,
            "rtype": relation_type,
            "doc_id": doc_id,
            "confidence": confidence,
            "context": context[:500]
        })
    
    def build_from_document(self, doc_id: str, entities: list[dict], relations: list[dict]):
        """Построить граф из извлечённых сущностей и связей документа"""
        # Создаём/обновляем сущности
        entity_map = {}  # name -> canonical_name
        
        for ent in entities:
            canonical = normalize_entity(ent.get("canonical_name", ent["name"]), ent.get("type"))
            entity_map[ent["name"]] = canonical
            
            self.create_entity(
                entity_id=str(ent.get("id", "")),
                name=ent["name"],
                canonical_name=canonical,
                entity_type=ent.get("type", "Unknown"),
                doc_id=doc_id,
                confidence=ent.get("confidence", 1.0),
                context=ent.get("context", "")
            )
        
        # Создаём связи
        for rel in relations:
            source_name = rel.get("source", "")
            target_name = rel.get("target", "")
            
            # Разрешаем имена в канонические
            source_canonical = entity_map.get(source_name, normalize_entity(source_name))
            target_canonical = entity_map.get(target_name, normalize_entity(target_name))
            
            self.create_relation(
                source_canonical=source_canonical,
                target_canonical=target_canonical,
                relation_type=rel.get("relation_type", "RELATED_TO"),
                doc_id=doc_id,
                confidence=rel.get("confidence", 1.0),
                context=rel.get("context", "")
            )
    
    def search_entities(self, query: str, entity_type: str | None = None,
                        limit: int = 10) -> list[dict]:
        """Поиск сущностей по названию"""
        if entity_type:
            result = neo4j_conn.query("""
                MATCH (e:Entity)
                WHERE e.canonical_name CONTAINS $query
                  AND e.type = $etype
                RETURN e.id as id, e.name as name, e.canonical_name as canonical_name,
                       e.type as type, e.confidence as confidence
                LIMIT $limit
            """, {"query": query, "etype": entity_type, "limit": limit})
        else:
            result = neo4j_conn.query("""
                MATCH (e:Entity)
                WHERE e.canonical_name CONTAINS $query
                RETURN e.id as id, e.name as name, e.canonical_name as canonical_name,
                       e.type as type, e.confidence as confidence
                LIMIT $limit
            """, {"query": query, "limit": limit})
        
        return result
    
    def get_neighbors(self, entity_name: str, depth: int = 2) -> dict[str, Any]:
        """Получить соседей сущности на заданную глубину"""
        # ВАЛИДАЦИЯ: защита от Cypher-инъекций и некорректных значений
        depth = max(1, min(int(depth), 5))
        
        # f-string для глубины — Cypher не поддерживает параметры в *1..$depth
        result = neo4j_conn.query(f"""
            MATCH path = (start:Entity {{canonical_name: $name}})-[:RELATION*1..{depth}]-(neighbor)
            RETURN start, neighbor, relationships(path) as rels, length(path) as depth
            LIMIT 100
        """, {"name": entity_name})
        
        nodes = {}
        edges = []
        
        for record in result:
            # Стартовый узел
            start = record["start"]
            nodes[start["canonical_name"]] = {
                "id": start.get("id", ""),
                "name": start["canonical_name"],
                "type": start["type"],
                "properties": {k: v for k, v in start.items() if k not in ["id", "name", "type"]}
            }
            
            # Сосед
            neighbor = record["neighbor"]
            nodes[neighbor["canonical_name"]] = {
                "id": neighbor.get("id", ""),
                "name": neighbor["canonical_name"],
                "type": neighbor["type"],
                "properties": {k: v for k, v in neighbor.items() if k not in ["id", "name", "type"]}
            }
            
            # Связи
            for rel in record["rels"]:
                edges.append({
                    "source": rel.start_node["canonical_name"],
                    "target": rel.end_node["canonical_name"],
                    "type": rel.get("type", "RELATION"),
                    "properties": {k: v for k, v in dict(rel).items() if k != "type"}
                })
        
        return {
            "nodes": list(nodes.values()),
            "edges": edges
        }
    
    def get_subgraph_for_entities(self, entity_names: list[str], depth: int = 2) -> dict[str, Any]:
        """Получить подграф для списка сущностей"""
        # ВАЛИДАЦИЯ: защита от Cypher-инъекций и некорректных значений
        depth = max(1, min(int(depth), 5))
        
        # f-string для глубины — Cypher не поддерживает параметры в *1..$depth
        result = neo4j_conn.query(f"""
            MATCH (e:Entity)
            WHERE e.canonical_name IN $names
            WITH e
            MATCH path = (e)-[:RELATION*1..{depth}]-(neighbor)
            RETURN e as start, neighbor, relationships(path) as rels
            LIMIT 200
        """, {"names": entity_names})
        
        nodes = {}
        edges = []
        
        for record in result:
            for node in [record["start"], record["neighbor"]]:
                nodes[node["canonical_name"]] = {
                    "id": node.get("id", ""),
                    "name": node["canonical_name"],
                    "type": node["type"],
                    "properties": {k: v for k, v in node.items() if k not in ["id", "name", "type"]}
                }
            
            for rel in record["rels"]:
                edges.append({
                    "source": rel.start_node["canonical_name"],
                    "target": rel.end_node["canonical_name"],
                    "type": rel.get("type", "RELATION"),
                    "properties": {k: v for k, v in dict(rel).items() if k != "type"}
                })
        
        return {
            "nodes": list(nodes.values()),
            "edges": edges
        }
    def delete_document(self, doc_id: str):
        """Удалить документ и связанные сущности (если нет других источников)"""
        neo4j_conn.query("""
            MATCH (d:Document {id: $doc_id})-[:CONTAINS]->(e:Entity)
            OPTIONAL MATCH (e)<-[:CONTAINS]-(other:Document)
            WHERE other.id <> $doc_id
            WITH e, collect(other) as others
            WHERE size(others) = 0
            DETACH DELETE e
        """, {"doc_id": doc_id})
        
        neo4j_conn.query("""
            MATCH (d:Document {id: $doc_id})
            DETACH DELETE d
        """, {"doc_id": doc_id})


graph_service = GraphService()