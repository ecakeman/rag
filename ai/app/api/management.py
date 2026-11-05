"""知识空间和摄取任务。不依赖旧的 filePath 契约。"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from sqlalchemy import text

from app.db import engine

router = APIRouter()
ROOT = Path(os.environ.get("KNOWLEDGE_STORAGE_ROOT", "/data/knowledge"))


def _auth(authorization: str | None) -> None:
    expected = os.environ.get("KNOWLEDGE_A2A_TOKEN", "")
    if expected and authorization != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="unauthorized")


@router.post("/spaces/{space_id}/documents")
async def upload(space_id: str, file: UploadFile = File(...), title: str = Form(""), authorization: str | None = Header(default=None)) -> dict:
    _auth(authorization)
    body = await file.read()
    digest = hashlib.sha256(body).hexdigest()
    suffix = Path(file.filename or "sample.md").suffix or ".md"
    ROOT.mkdir(parents=True, exist_ok=True)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO knowledge_space (id, name) VALUES (:id, :name) ON CONFLICT (id) DO NOTHING"),
                     {"id": space_id, "name": space_id})
        doc_id = conn.execute(text("INSERT INTO document (space_id, title) VALUES (:space, :title) RETURNING id"),
                              {"space": space_id, "title": title or file.filename or "document"}).scalar_one()
        version = conn.execute(text("""
            INSERT INTO document_version (document_id, version, checksum, storage_path, status)
            VALUES (:doc, 1, :checksum, :path, 'PENDING') RETURNING id
        """), {"doc": doc_id, "checksum": digest, "path": f"{doc_id}/1{suffix}"}).scalar_one()
        job_id = conn.execute(text("""
            INSERT INTO ingestion_job (document_version_id, status)
            VALUES (:version, 'PENDING') RETURNING id
        """), {"version": version}).scalar_one()
    path = ROOT / str(doc_id)
    path.mkdir(parents=True, exist_ok=True)
    (path / f"1{suffix}").write_bytes(body)
    return {"document_id": doc_id, "version_id": version, "job_id": job_id}


@router.get("/jobs/{job_id}")
def job(job_id: int, authorization: str | None = Header(default=None)) -> dict:
    _auth(authorization)
    with engine.connect() as conn:
        row = conn.execute(text("SELECT id, status, attempts, last_error FROM ingestion_job WHERE id=:id"), {"id": job_id}).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="job not found")
    return {"job_id": row[0], "status": row[1], "attempts": row[2], "last_error": row[3]}
