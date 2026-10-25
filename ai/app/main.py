"""FastAPI 入口(DESIGN §7):挂载路由、健康检查、schema 初始化、BM25 重建。"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import ingest, search
from app.db import init_db
from app.retrieval import bm25

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
        log.info("[startup] schema 初始化完成")
    except Exception:  # noqa: BLE001
        log.error("[startup] schema 初始化失败(稍后由请求路径重试)", exc_info=True)
    try:
        from app.config import settings
        if settings.bm25_init_on_startup:
            n = bm25.rebuild()
            log.info("[startup] BM25 索引重建完成: %d 子块", n)
    except Exception:  # noqa: BLE001
        log.warning("[startup] BM25 重建失败(空库首次启动属正常)", exc_info=True)
    yield


app = FastAPI(title="enterprise-doc-qa AI service", lifespan=lifespan)
app.include_router(ingest.router)
app.include_router(search.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
