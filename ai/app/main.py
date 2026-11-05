"""FastAPI 入口。Legacy RAG 与 Knowledge Agent 使用不同的表和路由。"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.config import settings

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger(__name__)
_schema_ready = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _schema_ready
    if settings.knowledge_agent_mode:
        try:
            from app.db import init_knowledge_db
            init_knowledge_db()
            _schema_ready = True
            log.info("[startup] knowledge schema 初始化完成")
        except Exception:
            _schema_ready = False
            log.error("[startup] knowledge schema 初始化失败", exc_info=True)
        if _schema_ready:
            try:
                from app.retrieval import bm25
                n = bm25.rebuild()
                log.info("[startup] 当前版本 BM25 索引: %d 子块", n)
            except Exception:
                from app.runtime.jobs import mark_index_dirty
                mark_index_dirty()
                log.warning("[startup] knowledge BM25 重建失败", exc_info=True)
            try:
                from app.runtime.jobs import start
                start()
            except Exception:
                log.warning("[startup] 摄取扫描未启动", exc_info=True)
    else:
        try:
            from app.db import init_legacy_db
            init_legacy_db()
            log.info("[startup] legacy schema 初始化完成")
        except Exception:
            log.error("[startup] legacy schema 初始化失败", exc_info=True)
        try:
            from app.retrieval import bm25
            if settings.bm25_init_on_startup:
                n = bm25.rebuild_legacy()
                log.info("[startup] legacy BM25 索引: %d 子块", n)
        except Exception:
            log.warning("[startup] legacy BM25 重建失败", exc_info=True)
        try:
            from app.runtime.mcp_probe import probe
            probe()
        except Exception:
            log.warning("[startup] MCP 目录探测失败，进程继续启动", exc_info=True)
    yield


app = FastAPI(title="enterprise-doc-qa AI service", lifespan=lifespan)

if settings.knowledge_agent_mode:
    from app.api import a2a, management
    app.include_router(a2a.router)
    app.include_router(management.router)
else:
    from app.api import chat, ingest, search
    app.include_router(ingest.router)
    app.include_router(search.router)
    app.include_router(chat.router)


@app.get("/health")
def health():
    if settings.knowledge_agent_mode and not _schema_ready:
        return JSONResponse(status_code=503, content={"status": "schema_unavailable"})
    return {"status": "ok"}
