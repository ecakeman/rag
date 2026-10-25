"""标题感知切分 + 父子分段(DESIGN §7.2.1)。

规则:
1. 按标题层级切 section,每个 section = 父块(is_parent=True, embedding=None)
2. section 内按 CHILD_TOKENS/OVERLAP_TOKENS 切子块
3. 无标题文档 → 按 PARENT_FALLBACK_TOKENS 滑窗当父块再切子块
4. markdown 表格行线性化为 "列:值; 列:值"
5. 超长 section(>2000)再切为多个父块
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.config import settings

TABLE_LINE = re.compile(r"^\s*\|.*\|\s*$")
SEP_LINE = re.compile(r"^\s*\|[\s:|-]+\|\s*$")
LONG_SECTION = 2000


@dataclass
class Chunk:
    content: str
    is_parent: bool
    section_path: str | None = None
    page: int | None = None
    token_count: int = 0
    parent_index: int | None = None  # 构建期指向父块下标;入库时替换为父块 id
    children: list[int] = field(default_factory=list)


def _split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """无 llama-index 依赖的确定性滑窗切分(按字符,中文场景字符≈token*1.5,
    设计允许:所有数值集中在 config,可整体调参)。"""
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]
    step = max(chunk_size - overlap, 1)
    return [text[i:i + chunk_size] for i in range(0, len(text), step) if text[i:i + chunk_size].strip()]


def linearize_tables(md: str) -> str:
    """markdown 表格 → "列1:值1; 列2:值2" 行(§7.2.1 规则4)。"""
    lines = md.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        if TABLE_LINE.match(lines[i]) and not SEP_LINE.match(lines[i]):
            header = [c.strip() for c in lines[i].strip().strip("|").split("|")]
            i += 1
            if i < len(lines) and SEP_LINE.match(lines[i]):
                i += 1  # 跳过分隔行
            while i < len(lines) and TABLE_LINE.match(lines[i]) and not SEP_LINE.match(lines[i]):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                pairs = [f"{h}:{v}" for h, v in zip(header, cells) if v]
                out.append("; ".join(pairs))
                i += 1
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)


def _sections(md: str, doc_title: str) -> list[tuple[str, str, int | None]]:
    """返回 [(section_path, section_text, page_hint)];按标题切分。"""
    lines = md.splitlines()
    sections: list[tuple[str, str, int | None]] = []
    stack: list[tuple[int, str]] = []  # (level, title)
    buf: list[str] = []

    def flush():
        text = "\n".join(buf).strip()
        if text:
            titles = [doc_title] + [t for _, t in stack]
            # 折叠连续重复层级(如文档自带与文档标题同名的 H1)
            collapsed = [titles[0]]
            for t in titles[1:]:
                if t != collapsed[-1]:
                    collapsed.append(t)
            sections.append((" > ".join(collapsed), text, None))
        buf.clear()

    for line in lines:
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            level = len(m.group(1))
            flush()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, m.group(2).strip()))
        else:
            buf.append(line)
    flush()
    return sections


def build_chunks(pages: list[tuple[int | None, str]], doc_title: str) -> list[Chunk]:
    """输入 [(page, md)] → 父子块列表(§7.2.1 全部规则)。"""
    chunks: list[Chunk] = []
    has_any_header = any(re.search(r"^#{1,6}\s+", md, re.M) for _, md in pages)

    for page, md in pages:
        md = linearize_tables(md)
        if has_any_header:
            sections = _sections(md, doc_title)
        else:
            # 无标题退化:按 PARENT_FALLBACK_TOKENS 滑窗造"伪 section"(§7.2.1 规则3)
            windows = _split_text(md, settings.parent_fallback_tokens, 0)
            sections = [(doc_title, w, page) for w in windows]

        for path, text, _hint in sections:
            first_page = page
            # 规则5:超长 section 再切
            parts = _split_text(text, settings.parent_fallback_tokens, 0) if len(text) > LONG_SECTION else [text]
            for part in parts:
                parent = Chunk(content=part, is_parent=True, section_path=path,
                               page=first_page, token_count=len(part))
                chunks.append(parent)
                p_idx = len(chunks) - 1
                for child_text in _split_text(part, settings.child_tokens, settings.overlap_tokens):
                    if not child_text.strip():
                        continue
                    # 注: 小于 child_tokens 的 section 会产生与父块同内容的唯一子块,
                    # 这是 small-to-big 的正常退化——子块才是可检索单元
                    chunks.append(Chunk(content=child_text, is_parent=False, section_path=path,
                                        page=first_page, token_count=len(child_text),
                                        parent_index=p_idx))
    return chunks
