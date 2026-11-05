"""非流式 A2A message/send。一次请求返回完整检索结果。"""
from __future__ import annotations

import hashlib
import json
import uuid

from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy import text

from app.application.retrieval import retrieve
from app.db import engine

router = APIRouter()


def _authorized(authorization: str | None) -> str:
    import os
    expected = os.environ.get("KNOWLEDGE_A2A_TOKEN", "")
    if not expected:
        return "anonymous"
    if authorization != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="a2a token rejected")
    return "java-integration"


def _payload(body: dict) -> dict:
    message = body.get("params", {}).get("message") or body.get("message") or {}
    for part in message.get("parts") or []:
        data = part.get("data") or part.get("text")
        if isinstance(data, dict) and (data.get("query") or data.get("invocationId")):
            return data
        if isinstance(data, str):
            try:
                parsed = json.loads(data)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
    return body.get("params") or body


@router.get("/.well-known/agent-card.json")
def agent_card(request: Request) -> dict:
    base = str(request.base_url).rstrip("/")
    return {
        "name": "knowledge-agent",
        "description": "返回知识库原文片段",
        "version": "1.0.0",
        "capabilities": {"streaming": False, "pushNotifications": False, "extendedAgentCard": False},
        "defaultInputModes": ["application/json"],
        "defaultOutputModes": ["application/json"],
        "skills": [{
            "id": "knowledge-retrieval",
            "name": "knowledge-retrieval",
            "description": "检索原文片段",
            "tags": ["retrieval"],
        }],
        "supportedInterfaces": [{
            "protocolBinding": "JSONRPC",
            "url": base + "/",
            "protocolVersion": "1.0",
        }],
    }


@router.post("/")
async def message_send(request: Request, authorization: str | None = Header(default=None)) -> dict:
    caller = _authorized(authorization)
    raw = await request.body()
    if not raw:
        raise HTTPException(status_code=400, detail="empty a2a body")
    try:
        body = json.loads(raw)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=400, detail="a2a body is not json") from error
    if body.get("method") not in (None, "message/send", "SendMessage"):
        raise HTTPException(status_code=400, detail="only message/send is supported")
    payload = _payload(body)
    invocation_id = str(payload.get("invocationId") or uuid.uuid4())
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    with engine.begin() as conn:
        row = conn.execute(text("""
            SELECT request_hash, status, result_json FROM knowledge_invocation
            WHERE caller_id=:caller AND invocation_id=:id
        """), {"caller": caller, "id": invocation_id}).fetchone()
        if row:
            if row[0] != digest:
                raise HTTPException(status_code=409, detail="idempotency conflict")
            if row[1] == "COMPLETED" and row[2]:
                result = row[2] if isinstance(row[2], dict) else json.loads(row[2])
                return _message(body, result)
            if row[1] == "RUNNING":
                raise HTTPException(status_code=409, detail="IN_PROGRESS")
        else:
            conn.execute(text("""
                INSERT INTO knowledge_invocation (caller_id, invocation_id, request_hash, status)
                VALUES (:caller, :id, :hash, 'RUNNING')
            """), {"caller": caller, "id": invocation_id, "hash": digest})
    try:
        result = await retrieve(str(payload.get("query") or ""), invocation_id, top_k=int((payload.get("constraints") or {}).get("topK") or 8))
        result.pop("hops", None)
    except Exception as error:
        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE knowledge_invocation SET status='FAILED', safe_message=:msg
                WHERE caller_id=:caller AND invocation_id=:id
            """), {"msg": str(error)[:300], "caller": caller, "id": invocation_id})
        raise HTTPException(status_code=502, detail="retrieval failed") from error
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE knowledge_invocation SET status='COMPLETED', result_json=CAST(:result AS jsonb)
            WHERE caller_id=:caller AND invocation_id=:id
        """), {"result": json.dumps(result, ensure_ascii=False), "caller": caller, "id": invocation_id})
    return _message(body, result)


def _message(body: dict, result: dict) -> dict:
    message = {
        "role": "ROLE_AGENT",
        "messageId": str(uuid.uuid4()),
        "parts": [{"data": result}],
    }
    if "jsonrpc" in body or body.get("method"):
        return {"jsonrpc": "2.0", "id": body.get("id"), "result": {"message": message}}
    return message
