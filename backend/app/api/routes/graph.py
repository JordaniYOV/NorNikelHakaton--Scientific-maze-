"""API endpoints для работы с графом знаний"""
from fastapi import APIRouter, HTTPException

from app.core.schemas import GraphResponse, GraphQueryRequest, GraphNode
from app.core.services.graph import graph_service
from app.db.database import neo4j_conn


router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/entity/{name}", response_model=GraphResponse)
def get_entity_neighbors(name: str, depth: int = 2):
    """Получить соседей сущности"""
    try:
        result = graph_service.get_neighbors(name, depth)
        return GraphResponse(**result)
    except Exception as e:
        raise HTTPException(500, f"Ошибка: {str(e)}")


@router.post("/subgraph", response_model=GraphResponse)
def get_subgraph(request: GraphQueryRequest):
    """Получить подграф по Cypher-запросу (ограниченный)"""
    # Для MVP: только безопасные запросы на чтение
    if any(kw in request.cypher.upper() for kw in ["DELETE", "REMOVE", "SET", "CREATE", "MERGE"]):
        raise HTTPException(403, "Только запросы на чтение разрешены")
    
    try:
        result = neo4j_conn.query(request.cypher, request.parameters or {})
        
        # Преобразуем результат в граф
        nodes = {}
        edges = []
        
        for record in result:
            for key, value in record.items():
                if hasattr(value, "labels"):  # Node
                    nodes[value["canonical_name"]] = GraphNode(
                        id=value.get("id", ""),
                        name=value["canonical_name"],
                        canonical_name=value["canonical_name"],
                        type=list(value.labels)[0] if value.labels else "Entity",
                        properties={k: v for k, v in dict(value).items() 
                                  if k not in ["id", "canonical_name"]}
                    )
                elif hasattr(value, "type"):  # Relationship
                    edges.append({
                        "source": value.start_node["canonical_name"],
                        "target": value.end_node["canonical_name"],
                        "type": value.type,
                        "properties": dict(value)
                    })
        
        return GraphResponse(
            nodes=list(nodes.values()),
            edges=edges
        )
    except Exception as e:
        raise HTTPException(500, f"Ошибка выполнения запроса: {str(e)}")


@router.get("/search", response_model=list[GraphNode])
def search_entities(q: str, type: str | None = None, limit: int = 10):
    """Поиск сущностей в графе"""
    results = graph_service.search_entities(q, type, limit)
    return [
        GraphNode(
            id=r.get("id", ""),
            name=r["name"],
            canonical_name=r["canonical_name"],
            type=r["type"],
            properties={"confidence": r.get("confidence", 1.0)}
        )
        for r in results
    ]