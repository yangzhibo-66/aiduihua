from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # 基本配置
    PROJECT_NAME: str = "AI RAG 知识库系统"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"

    # JWT 配置
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 30  # 30 days

    # 数据库配置
    DATABASE_URL: str

    # 文件上传配置
    UPLOAD_DIR: str
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50 MB
    ALLOWED_EXTENSIONS: set = {".pdf", ".docx", ".txt", ".md"}
    IMAGE_EXTENSIONS: set = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
    MAX_IMAGE_SIZE: int = 50 * 1024 * 1024  # 50 MB

    # AI 配置（阿里云百炼 - OpenAI 兼容模式）
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: Optional[str] = None
    DEFAULT_MODEL: str
    IMAGE_OCR_MODEL: Optional[str] = None

    # 阿里云百炼嵌入模型配置
    DASHSCOPE_API_KEY: Optional[str] = None
    EMBEDDING_BASE_URL: Optional[str] = None
    EMBEDDING_MODEL: str

    # 向量数据库配置
    FAISS_DIR: str
    VECTOR_STORE_BACKEND: str = "chroma"
    VECTOR_STORE_FALLBACK: str = "mock"
    CHROMA_DIR: str = "chroma_db"
    CHROMA_COLLECTION: str = "rag_chunks"
    CHROMA_EMBEDDING_DIMENSION: int = 384

    class Config:
        env_file = ".env"
        extra = "ignore"  # 忽略 .env 中多余的字段


settings = Settings()