"""/chat 路由(DESIGN §5.2):SSE 流。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.agent.chat_service import stream_chat
from app.api.ingest import require_token
from pydantic import BaseModel, Field

router = APIRouter()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    sessionId: int | None = None
    messageId: int | None = None
    message: str = Field(min_length=1)
    history: list[ChatMessage] = Field(default_factory=list, max_length=6)


@router.post("/chat", dependencies=[Depends(require_token)])
async def chat(req: ChatRequest) -> StreamingResponse:
    return StreamingResponse(
        stream_chat(req.model_dump()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
