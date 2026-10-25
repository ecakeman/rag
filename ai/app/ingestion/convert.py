"""文档 → Markdown 统一转换(DESIGN §3/§7.2b)。

pdf  → pymupdf4llm page_chunks 模式(逐页,保留页码)
docx → mammoth(无页码)
md/txt → 直读(无页码)
返回 [(page:int|None, markdown_text), ...]
"""
from __future__ import annotations

from pathlib import Path


def to_markdown(file_path: str) -> list[tuple[int | None, str]]:
    path = Path(file_path)
    ext = path.suffix.lstrip(".").lower()
    if ext == "pdf":
        return _pdf(path)
    if ext == "docx":
        return [(None, _docx(path))]
    if ext in ("md", "markdown"):
        return [(None, path.read_text(encoding="utf-8"))]
    if ext == "txt":
        return [(None, path.read_text(encoding="utf-8"))]
    raise ValueError(f"不支持的文件类型: {ext}")


def _pdf(path: Path) -> list[tuple[int, str]]:
    import pymupdf4llm  # 延迟导入,避免单测强依赖

    pages = pymupdf4llm.to_markdown(str(path), page_chunks=True)
    result = []
    for p in pages:
        text = p.get("text", "").strip()
        if text:
            page_no = p.get("metadata", {}).get("page")
            result.append((int(page_no) + 1 if page_no is not None else None, text))
    return result or [(1, "")]


def _docx(path: Path) -> str:
    import mammoth

    with open(path, "rb") as f:
        return mammoth.convert_to_markdown(f).value
