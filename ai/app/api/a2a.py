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
_LEASE_SECONDS = 45


def _authorized(authorization: str | None) -> str:
    import os
    expected = os.environ.get("KNOWLEDGE_A2A_TOKEN", "")
    if not expected or authorization != f"Bearer {expected}":
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


def _claim(caller: str, invocation_id: str, digest: str) -> tuple[str, int | None, str | None, dict | None]:
    """原子占位。返回 (RUN|COMPLETED|IN_PROGRESS|CONFLICT, fencing_token, lease_owner, cached)。"""
    owner = str(uuid.uuid4())
    params = {"caller": caller, "id": invocation_id, "hash": digest, "owner": owner, "lease": _LEASE_SECONDS}
    with engine.begin() as conn:
        inserted = conn.execute(text("""
            INSERT INTO knowledge_invocation
                (caller_id, invocation_id, request_hash, status, lease_owner, lease_until, attempts, fencing_token)
            VALUES (:caller, :id, :hash, 'RUNNING', :owner, now() + make_interval(secs => :lease), 1, 1)
            ON CONFLICT (caller_id, invocation_id) DO NOTHING
            RETURNING fencing_token
        """), params).fetchone()
        if inserted:
            return "RUN", int(inserted[0]), owner, None
        row = conn.execute(text("""
            SELECT request_hash, status, result_json,
                   lease_until IS NOT NULL AND lease_until > now()
            FROM knowledge_invocation
            WHERE caller_id=:caller AND invocation_id=:id
        """), params).fetchone()
        if row is None:
            return "IN_PROGRESS", None, None, None
        if row[0] != digest:
            return "CONFLICT", None, None, None
        if row[1] == "COMPLETED" and row[2] is not None:
            cached = row[2] if isinstance(row[2], dict) else json.loads(row[2])
            return "COMPLETED", None, None, cached
        if row[1] == "RUNNING" and row[3]:
            return "IN_PROGRESS", None, None, None
        claimed = conn.execute(text("""
            UPDATE knowledge_invocation
            SET status='RUNNING', lease_owner=:owner,
                lease_until=now() + make_interval(secs => :lease),
                attempts=attempts + 1, fencing_token=fencing_token + 1,
                result_json=NULL, safe_message=NULL
            WHERE caller_id=:caller AND invocation_id=:id AND request_hash=:hash
              AND (
                status IN ('FAILED', 'TIMED_OUT', 'UNKNOWN')
                OR (status = 'RUNNING' AND (lease_until IS NULL OR lease_until <= now()))
                OR (status = 'COMPLETED' AND result_json IS NULL)
              )
            RETURNING fencing_token
        """), params).fetchone()
        if claimed:
            return "RUN", int(claimed[0]), owner, None
    return "IN_PROGRESS", None, None, None


def _finish(caller: str, invocation_id: str, token: int, owner: str, status: str,
            result: dict | None = None, message: str | None = None) -> bool:
    with engine.begin() as conn:
        row = conn.execute(text("""
            UPDATE knowledge_invocation
            SET status=:status,
                result_json=CASE WHEN :result IS NULL THEN NULL ELSE CAST(:result AS jsonb) END,
                safe_message=:msg, lease_until=NULL
            WHERE caller_id=:caller AND invocation_id=:id
              AND fencing_token=:token AND lease_owner=:owner
            RETURNING invocation_id
        """), {
            "status": status, "result": None if result is None else json.dumps(result, ensure_ascii=False),
            "msg": None if message is None else message[:300],
            "caller": caller, "id": invocation_id, "token": token, "owner": owner,
        }).fetchone()
    return row is not None


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
    outcome, token, owner, cached = _claim(caller, invocation_id, digest)
    if outcome == "CONFLICT":
        raise HTTPException(status_code=409, detail="idempotency conflict")
    if outcome == "COMPLETED":
        return _message(body, cached or {})
    if outcome != "RUN" or token is None or owner is None:
        raise HTTPException(status_code=409, detail="IN_PROGRESS")
    try:
        spaces = payload.get("knowledgeSpaceIds")
        space_ids = [str(item).strip() for item in spaces if str(item).strip()] if isinstance(spaces, list) else []
        if not space_ids:
            result = {"schemaVersion": "knowledge-retrieval-result-v1", "invocationId": invocation_id, "results": []}
        else:
            context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
            top_k = int((payload.get("constraints") or {}).get("topK") or 8)
            result = await retrieve(
                str(payload.get("query") or ""), invocation_id,
                top_k=top_k, knowledge_space_ids=space_ids, context=context,
            )
        result.pop("hops", None)
    except Exception as error:
        _finish(caller, invocation_id, token, owner, "FAILED", message=str(error))
        raise HTTPException(status_code=502, detail="retrieval failed") from error
    if not _finish(caller, invocation_id, token, owner, "COMPLETED", result=result):
        raise HTTPException(status_code=409, detail="IN_PROGRESS")
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
