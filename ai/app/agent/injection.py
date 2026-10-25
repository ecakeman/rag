"""注入缓解(DESIGN §11.4.3):正则黑名单命中 → trace warning(不中断)。"""
from __future__ import annotations

import re

PATTERNS = [
    re.compile(r"忽略(以上|上述|之前)?(的)?(所有)?指令", re.I),
    re.compile(r"无视(以上|上述).{0,6}(指令|要求)", re.I),
    re.compile(r"输出(你的|你的)?(提示词|系统提示|system prompt)", re.I),
    re.compile(r"reveal (your )?(system )?prompt", re.I),
    re.compile(r"disregard (all )?(previous |above )?instructions", re.I),
    re.compile(r"你现在是.{0,10}(开发者模式|DAN)", re.I),
]


def scan_injection(text: str) -> str | None:
    """命中返回命中片段(用于 trace warning),未命中返回 None。"""
    if not text:
        return None
    for p in PATTERNS:
        m = p.search(text)
        if m:
            return m.group(0)[:40]
    return None
