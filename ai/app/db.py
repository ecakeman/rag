"""数据库引擎与按运行模式初始化 schema。"""
from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import settings

LEGACY_SCHEMA = Path(__file__).parent / "schema.sql"
KNOWLEDGE_SCHEMA = Path(__file__).parent / "schema_knowledge.sql"

log = logging.getLogger(__name__)
engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


def statements(ddl: str) -> list[str]:
    """丢掉整行注释后再按分号分句。Schema 里不能出现带分号的字符串。"""
    lines = [line for line in ddl.splitlines() if not line.strip().startswith("--")]
    return [part.strip() for part in "\n".join(lines).split(";") if part.strip()]


def _apply(path: Path) -> None:
    ddl = path.read_text(encoding="utf-8").replace("__EMBED_DIM__", str(settings.embed_dim))
    with engine.connect() as conn:
        try:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
        except Exception:
            conn.rollback()
            log.warning("[schema] vector extension was not created by this role")
        for stmt in statements(ddl):
            conn.execute(text(stmt))
            conn.commit()


def init_legacy_db() -> None:
    _apply(LEGACY_SCHEMA)


def init_knowledge_db() -> None:
    _apply(KNOWLEDGE_SCHEMA)


def init_db() -> None:
    if settings.knowledge_agent_mode:
        init_knowledge_db()
    else:
        init_legacy_db()
