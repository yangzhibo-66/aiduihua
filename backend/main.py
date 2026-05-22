import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
import database
import models
from routers import user, documents, chat

# 初始化数据库
models.Base.metadata.create_all(bind=database.engine)


def _ensure_documents_schema() -> None:
    inspector = inspect(database.engine)
    tables = set(inspector.get_table_names())
    if "documents" not in tables:
        return

    columns = {c["name"] for c in inspector.get_columns("documents")}
    with database.engine.begin() as conn:
        if "content_type" not in columns:
            conn.execute(text("ALTER TABLE documents ADD COLUMN content_type VARCHAR(20) DEFAULT 'text'"))
        if "extra_metadata" not in columns:
            conn.execute(text("ALTER TABLE documents ADD COLUMN extra_metadata TEXT"))
        if "category_id" not in columns:
            conn.execute(text("ALTER TABLE documents ADD COLUMN category_id INTEGER"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_documents_category_id ON documents (category_id)"))


def _ensure_categories_schema() -> None:
    models.DocumentCategory.__table__.create(bind=database.engine, checkfirst=True)


_ensure_documents_schema()
_ensure_categories_schema()

app = FastAPI(title="AI 知识库 API", version="1.0.0")

# ==============================================
# CORS配置（开发宽松 / 生产收紧）
# ==============================================
APP_ENV = os.getenv("APP_ENV", "dev").strip().lower()

if APP_ENV in ("prod", "production"):
    raw = os.getenv("CORS_ALLOW_ORIGINS", "")
    allowed_origins = [o.strip() for o in raw.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
        expose_headers=["*"],
        max_age=3600,
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ],
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
        max_age=3600,
    )

# ==============================================
# 路由配置 - 关键修复点
# ==============================================
# 注意：user.router 内部已经有 prefix="/user"
# 所以这里不要再加 /api 前缀，或者改为空字符串
app.include_router(user.router, prefix="/api")  # 最终路径: /api/user/login
# 或者如果其他路由也有 prefix，保持一致
app.include_router(documents.router, prefix="/api")
app.include_router(chat.router, prefix="/api")

@app.get("/health")
def health():
    return {"status": "ok"}

