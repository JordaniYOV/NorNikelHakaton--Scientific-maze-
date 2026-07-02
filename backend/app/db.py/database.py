from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from neo4j import GraphDatabase
from qdrant_client import QdrantClient
import redis
from ..core.config import settings


# PostgreSQL
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)



def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Neo4j
class Neo4jConnection:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
    
    def close(self):
        self.driver.close()
    
    def query(self, query, parameters=None):
        with self.driver.session() as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]
    
    def execute_write(self, query, parameters=None):
        with self.driver.session() as session:
            return session.execute_write(lambda tx: tx.run(query, parameters or {}).data())


neo4j_conn = Neo4jConnection()


# Qdrant
qdrant_client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)


# Redis
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)


def init_qdrant_collection():
    """Инициализация коллекции в Qdrant"""
    from qdrant_client.models import Distance, VectorParams
    
    collections = qdrant_client.get_collections().collections
    collection_names = [c.name for c in collections]
    
    if settings.QDRANT_COLLECTION not in collection_names:
        qdrant_client.create_collection(
            collection_name=settings.QDRANT_COLLECTION,
            vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
        )
        print(f"Collection '{settings.QDRANT_COLLECTION}' created")