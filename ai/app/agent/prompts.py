"""Prompt 资产管理(DESIGN §11.2):yaml 文件化 + PROMPT_PACK 指纹 + str.format 渲染。"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import yaml

from app.config import settings

_DIR = Path(__file__).parent / "prompts"

# yaml 正文中的字面花括号以 {{ }} 转义,str.format 渲染后还原为单括号


@dataclass(frozen=True)
class PromptSpec:
    id: str
    name: str
    version: int
    roles: dict[str, str]  # {"user": ...} 或 {"system": ..., "user": ...}


def _load_all() -> dict[str, PromptSpec]:
    specs: dict[str, PromptSpec] = {}
    for f in sorted(_DIR.glob("*.yaml")):
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        specs[data["id"]] = PromptSpec(id=data["id"], name=data["name"],
                                       version=int(data.get("version", 1)),
                                       roles=data["roles"])
    if not specs:
        raise RuntimeError(f"prompts 目录为空: {_DIR}")
    return specs


_CACHE: dict[str, PromptSpec] | None = None


def all_prompts() -> dict[str, PromptSpec]:
    global _CACHE
    if _CACHE is None:
        _CACHE = _load_all()
    return _CACHE


def compute_prompt_pack() -> str:
    """对 prompts 目录全部文件内容的 sha1 前 8 位(§11.2.2)。"""
    h = hashlib.sha1()
    for f in sorted(_DIR.glob("*.yaml")):
        h.update(f.name.encode())
        h.update(f.read_bytes())
    return h.hexdigest()[:8]


def render(prompt_id: str, **variables) -> list[dict[str, str]]:
    """渲染为消息列表;顺序固定 system→user(§11.2.1)。"""
    spec = all_prompts().get(prompt_id)
    if spec is None:
        raise KeyError(f"未知 prompt: {prompt_id}")
    messages: list[dict[str, str]] = []
    for role in ("system", "user"):
        if role in spec.roles:
            try:
                content = spec.roles[role].format(**variables)
            except (KeyError, IndexError, ValueError) as e:
                raise RuntimeError(f"prompt {prompt_id} 变量渲染失败: {e}") from e
            messages.append({"role": role, "content": content})
    return messages


def refresh_pack() -> str:
    settings.prompt_pack = compute_prompt_pack()
    return settings.prompt_pack


# 模块加载即计算指纹并写回 settings(§7.1 PROMPT_PACK)
PROMPT_PACK = refresh_pack()
