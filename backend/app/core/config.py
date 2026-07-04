from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+psycopg://postgres:1234@localhost:5430/kg_mvp"
    
    # Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    
    # Qdrant
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "chunks"
    QDRANT_VECTOR_SIZE: int = 768
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # OpenAI
    YANDEX_API_KEY: str = "AQVNw1jAUmBRQz2_HKguH78oeLe2BH-6gNFhWsBs"
    YANDEX_FOLDER_ID: str = "b1ggusvist6c2sia1dno"
    YANDEX_BASE_URL: str = "https://ai.api.cloud.yandex.net/v1"
    YANDEX_MODEL: str = "aliceai-llm"
    
    #Local models (Ollama)
    OLLAMA_EMBED_URL: str = "http://localhost:11435"
    OLLAMA_CHAT_URL: str = "http://localhost:11434"
    OLLAMA_CHAT_MODEL: str ="qwen2.5:3b"
    OLLAMA_EMBED_MODEL: str ="nomic-embed-text"

    # Uploads
    UPLOAD_DIR: str = "./uploads/raw"
    
    # Chunking
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    
    # App
    DEBUG: bool = True
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()