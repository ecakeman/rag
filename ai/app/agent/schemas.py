"""LLM 输出 schema(DESIGN §11.3):pydantic 模型,失败降级值由调用方以 fallback 闭包给出。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RewriteOut(BaseModel):
    query: str


class RouterOut(BaseModel):
    type: Literal["SIMPLE", "COMPLEX", "CHITCHAT"]
    reason: str = ""


class DecomposeOut(BaseModel):
    subQuestions: list[str] = Field(default_factory=list)


class GradeItem(BaseModel):
    id: int
    score: int


class GradeOut(BaseModel):
    items: list[GradeItem] = Field(default_factory=list)


class SufficiencyOut(BaseModel):
    verdict: Literal["ENOUGH", "NEED_MORE"]
    missing: str = ""


class VerifyOut(BaseModel):
    verdict: Literal["PASS", "FAIL"]
    unsupported: str = ""


class JudgeOut(BaseModel):
    grade: Literal["full", "partial", "wrong"]
    reason: str = ""


# 节点 → 输出 schema 映射(节点级降级默认值见各调用处 fallback)
NODE_SCHEMAS: dict[str, type[BaseModel]] = {
    "rewrite": RewriteOut,
    "router": RouterOut,
    "decompose": DecomposeOut,
    "grade": GradeOut,
    "sufficiency": SufficiencyOut,
    "verify": VerifyOut,
}
