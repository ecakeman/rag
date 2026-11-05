"""启动时探测 Java MCP Gateway。目录为空或不可达都不阻止进程启动。"""
from __future__ import annotations

import logging
import os

import httpx

log = logging.getLogger(__name__)


def probe() -> None:
    endpoint = os.environ.get("KNOWLEDGE_MCP_ENDPOINT", "")
    if not endpoint:
        log.info("[startup] 未配置 MCP 目录")
        return
    token = os.environ.get("KNOWLEDGE_MCP_TOKEN", "")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "knowledge-agent", "version": "0.1"},
        },
    }
    try:
        response = httpx.post(endpoint, json=body, headers=headers, timeout=3)
        log.info("[startup] MCP initialize status=%s", response.status_code)
    except Exception:  # noqa: BLE001
        log.warning("[startup] MCP Gateway 不可达，进程继续启动", exc_info=True)
