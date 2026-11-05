"""知识空间和摄取任务。不依赖旧的 filePath 契约。"""
from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from sqlalchemy import text

from app.config import settings
from app.db import engine

router = APIRouter()
ROOT = Path(os.environ.get("KNOWLEDGE_STORAGE_ROOT", "/data/knowledge"))
_SUFFIXES = {".md", ".txt", ".pdf", ".html", ".htm", ".docx"}
_CHUNK = 1024 * 1024


def _auth(authorization: str | None) -> None:
    expected = os.environ.get("KNOWLEDGE_A2A_TOKEN", "")
    if not expected or authorization != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="unauthorized")


def _suffix(filename: str | None) -> str:
    name = Path(filename or "sample.md").name
    suffix = Path(name).suffix.lower()
    if suffix not in _SUFFIXES or "/" in suffix or "\\" in suffix or ".." in name:
        raise HTTPException(status_code=400, detail="unsupported file suffix")
    return suffix


@router.post("/spaces/{space_id}/documents")
async def upload(space_id: str, file: UploadFile = File(...), title: str = Form(""),
                 document_id: int | None = Form(None),
                 authorization: str | None = Header(default=None)) -> dict:
    _auth(authorization)
    suffix = _suffix(file.filename)
    ROOT.mkdir(parents=True, exist_ok=True)
    temporary = ROOT / f".upload-{uuid.uuid4().hex}.tmp"
    digest = hashlib.sha256()
    total = 0
    final: Path | None = None
    moved = False
    try:
        with temporary.open("wb") as out:
            while True:
                chunk = await file.read(_CHUNK)
                if not chunk:
                    break
                total += len(chunk)
                if total > settings.knowledge_upload_max_bytes:
                    raise HTTPException(status_code=413, detail="file exceeds upload limit")
                digest.update(chunk)
                out.write(chunk)
        if total == 0:
            raise HTTPException(status_code=400, detail="empty file")
        checksum = digest.hexdigest()
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO knowledge_space (id, name) VALUES (:id, :name)
                ON CONFLICT (id) DO NOTHING
            """), {"id": space_id, "name": space_id})
            if document_id is None:
                doc_id = conn.execute(text("""
                    INSERT INTO document (space_id, title) VALUES (:space, :title) RETURNING id
                """), {"space": space_id, "title": title or file.filename or "document"}).scalar_one()
                version_no = 1
            else:
                row = conn.execute(text("""
                    SELECT id, space_id FROM document WHERE id=:id FOR UPDATE
                """), {"id": document_id}).fetchone()
                if row is None or row[1] != space_id:
                    raise HTTPException(status_code=404, detail="document is not in this space")
                doc_id = int(row[0])
                if title:
                    conn.execute(text("UPDATE document SET title=:title WHERE id=:id"),
                                 {"title": title, "id": doc_id})
                version_no = int(conn.execute(text("""
                    SELECT COALESCE(MAX(version), 0) + 1 FROM document_version WHERE document_id=:id
                """), {"id": doc_id}).scalar_one())
            storage = f"{doc_id}/{version_no}{suffix}"
            final = ROOT / storage
            final.parent.mkdir(parents=True, exist_ok=True)
            if final.exists():
                raise HTTPException(status_code=409, detail="version file already exists")
            os.replace(temporary, final)
            moved = True
            version_id = conn.execute(text("""
                INSERT INTO document_version (document_id, version, checksum, storage_path, status)
                VALUES (:doc, :version, :checksum, :path, 'PENDING') RETURNING id
            """), {"doc": doc_id, "version": version_no, "checksum": checksum, "path": storage}).scalar_one()
            job_id = conn.execute(text("""
                INSERT INTO ingestion_job (document_version_id, status)
                VALUES (:version, 'PENDING') RETURNING id
            """), {"version": version_id}).scalar_one()
        return {"document_id": doc_id, "version_id": version_id, "version": version_no, "job_id": job_id}
    except Exception:
        if moved and final is not None and final.exists():
            final.unlink()
        raise
    finally:
        if temporary.exists():
            temporary.unlink()


@router.get("/jobs/{job_id}")
def job(job_id: int, authorization: str | None = Header(default=None)) -> dict:
    _auth(authorization)
    with engine.connect() as conn:
        row = conn.execute(text("SELECT id, status, attempts, last_error FROM ingestion_job WHERE id=:id"), {"id": job_id}).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="job not found")
    return {"job_id": row[0], "status": row[1], "attempts": row[2], "last_error": row[3]}
