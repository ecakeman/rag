"""/search 路由(DESIGN §5.2)。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.api.ingest import require_token
from app.retrieval.service import hits_with_parents, hybrid_search

router = APIRouter()


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    docIds: list[int] | None = None
    topK: int | None = Field(default=None, ge=1, le=20)


@router.post("/search", dependencies=[Depends(require_token)])
def search(req: SearchRequest) -> dict:
    try:
        hits = hybrid_search(req.query, doc_ids=req.docIds, top_k=req.topK)
        return {"items": hits_with_parents(hits)}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=5032, detail=f"检索失败: {e}") from e
