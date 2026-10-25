"""数据库引擎与 schema 初始化(DESIGN §4.3)。"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import settings

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


def init_db() -> None:
    """幂等执行 schema.sql;vector 维度按 EMBED_DIM 模板替换(§4.3/§7.1)。"""
    ddl = SCHEMA_PATH.read_text(encoding="utf-8")
    ddl = ddl.replace("__EMBED_DIM__", str(settings.embed_dim))
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        for stmt in [s.strip() for s in ddl.split(";") if s.strip() and not s.strip().startswith("--")]:
            conn.execute(text(stmt))
