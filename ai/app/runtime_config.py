"""运行时配置覆盖：system_config 表(系统设置页写入)优先于环境变量。

设计要点(DESIGN §13 系统管理)：
- 管理端在页面上填 LLM/Embedding/Rerank 的连接信息，写入 system_config 表；
- 本模块以 TTL 缓存读取该表，各客户端构造点用 cfg() 取值实现免重启生效；
- 表未创建或读库失败时降级为空覆盖，等价于纯环境变量行为。
"""
from __future__ import annotations

import threading
import time

from sqlalchemy import text

from app.db import engine

_CACHE_TTL = 15.0
_LOCK = threading.Lock()
_CACHE: dict[str, str] = {}
_LOADED_AT = 0.0


def _load_locked() -> None:
    global _CACHE, _LOADED_AT
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT key, value FROM system_config")).fetchall()
        _CACHE = {str(r[0]): str(r[1]) for r in rows}
    except Exception:  # noqa: BLE001  表未建/瞬时故障:降级为空覆盖
        _CACHE = {}
    _LOADED_AT = time.time()


def overrides() -> dict[str, str]:
    """当前 DB 覆盖表(带 TTL 缓存)。"""
    with _LOCK:
        if time.time() - _LOADED_AT > _CACHE_TTL:
            _load_locked()
        return _CACHE


def cfg(key: str, default: str = "") -> str:
    """取配置：DB 覆盖优先，空值回落 default(通常是 settings 的环境变量值)。"""
    v = overrides().get(key)
    return v if v not in (None, "") else default
