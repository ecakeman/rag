"""FastAPI 入口(DESIGN §7):挂载路由、健康检查、schema 初始化。"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import ingest
from app.db import init_db

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
    yield


app = FastAPI(title="enterprise-doc-qa AI service", lifespan=lifespan)
app.include_router(ingest.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
