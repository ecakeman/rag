"""/ingest 路由(DESIGN §5.2):X-Internal-Token 保护。"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from pydantic import BaseModel

from app.config import settings
from app.ingestion import pipeline

router = APIRouter()

WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE_ROOT", "/workspaces/enterprise-doc-qa"))


def require_token(x_internal_token: str = Header(default="")) -> None:
    if x_internal_token != settings.internal_token:
        raise HTTPException(status_code=401, detail="internal token 无效")


class IngestRequest(BaseModel):
    docId: int
    filePath: str
    fileName: str
    title: str
    callbackUrl: str


@router.post("/ingest", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_token)])
def ingest(req: IngestRequest, background: BackgroundTasks) -> dict:
    file_path = (WORKSPACE_ROOT / req.filePath).resolve()
    background.add_task(pipeline.run_ingest, req.docId, str(file_path),
                        req.fileName, req.title, req.callbackUrl)
    return {"status": "QUEUED"}


@router.get("/ingest/{doc_id}/status", dependencies=[Depends(require_token)])
def ingest_status(doc_id: int) -> dict:
    return pipeline.ingest_status(doc_id)


@router.delete("/ingest/{doc_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_token)])
def delete_ingest(doc_id: int) -> None:
    pipeline.delete_doc_chunks(doc_id)
