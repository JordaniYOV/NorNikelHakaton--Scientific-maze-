"""Главный файл приложения FastAPI"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.database import engine, init_qdrant_collection
from app.api.routes import documents, search, graph


# Инициализация Qdrant
init_qdrant_collection()

# Создание приложения
app = FastAPI(
    title="Knowledge Graph MVP",
    description="Интеллектуальная система поиска и анализа научно-технических данных",
    version="0.1.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Роутеры
app.include_router(documents.router)
app.include_router(search.router)
app.include_router(graph.router)


@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "Knowledge Graph MVP",
        "version": "0.1.0",
        "endpoints": {
            "documents": "/documents",
            "search": "/search",
            "graph": "/graph"
        }
    }


@app.get("/health")
def health_check():
    """Проверка здоровья системы"""
    import redis
    from app.db.database import redis_client, qdrant_client, neo4j_conn
    
    checks = {
        "api": "ok",
        "postgres": "unknown",
        "neo4j": "unknown",
        "qdrant": "unknown",
        "redis": "unknown"
    }
    
    # PostgreSQL
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"error: {str(e)}"
    
    # Neo4j
    try:
        neo4j_conn.query("RETURN 1 as test")
        checks["neo4j"] = "ok"
    except Exception as e:
        checks["neo4j"] = f"error: {str(e)}"
    
    # Qdrant
    try:
        qdrant_client.get_collections()
        checks["qdrant"] = "ok"
    except Exception as e:
        checks["qdrant"] = f"error: {str(e)}"
    
    # Redis
    try:
        redis_client.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {str(e)}"
    
    all_ok = all(v == "ok" for v in checks.values() if v != "api")
    
    return {
        "status": "healthy" if all_ok else "degraded",
        "checks": checks
    }