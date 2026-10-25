"""M1W2-2 验收:标题感知切分/父子结构/退化规则/表格线性化/超长切分。"""
from app.config import settings
from app.ingestion.chunker import build_chunks, linearize_tables


def md(text: str) -> list[tuple[None, str]]:
    return [(None, text)]


def test_header_sections_become_parents():
    text = "# 员工手册\n## 假期\n年假为 5 天，工作满 10 年为 10 天。\n## 报销\n发票需在 30 天内提交。"
    chunks = build_chunks(md(text), "员工手册")
    parents = [c for c in chunks if c.is_parent]
    children = [c for c in chunks if not c.is_parent]
    assert len(parents) == 2  # 两个 H2 section
    paths = {p.section_path for p in parents}
    assert "员工手册 > 假期" in paths and "员工手册 > 报销" in paths
    assert all(c.parent_index is not None for c in children)
    # 每个子块的 parent_index 指向存在的父块
    assert all(0 <= c.parent_index < len(chunks) for c in children)


def test_children_within_size_and_overlap():
    long_section = "假" * (settings.child_tokens * 5)  # 足够切成多块
    text = f"# 手册\n## 长节\n{long_section}"
    chunks = build_chunks(md(text), "手册")
    children = [c for c in chunks if not c.is_parent]
    assert len(children) >= 4
    assert all(len(c.content) <= settings.child_tokens for c in children)
    # 相邻子块应有重叠(前一块尾部出现在后一块头部区域)
    assert children[0].content[-10:] in children[1].content


def test_no_header_fallback_sliding_parents():
    text = "无标题长文本。" * 400  # 无任何 # 标题
    chunks = build_chunks(md(text), "纯文本文档")
    parents = [c for c in chunks if c.is_parent]
    assert len(parents) >= 2
    assert all(p.section_path == "纯文本文档" for p in parents)
    # 父块无重叠
    assert all(len(p.content) <= settings.parent_fallback_tokens for p in parents)


def test_table_linearization():
    tbl = "| 项目 | 天数 |\n|---|---|\n| 年假 | 5 |\n| 病假 | 15 |"
    out = linearize_tables(tbl)
    assert "项目:年假; 天数:5" in out
    assert "项目:病假; 天数:15" in out
    assert "|" not in out


def test_table_rows_flow_into_chunks():
    text = "# 制度\n" + "| 项目 | 天数 |\n|---|---|\n| 年假 | 5 |\n"
    chunks = build_chunks(md(text), "制度")
    joined = "\n".join(c.content for c in chunks)
    assert "项目:年假; 天数:5" in joined


def test_long_section_split_into_multiple_parents():
    body = "字" * 5000  # >2000 触发规则5
    text = f"# 手册\n## 巨节\n{body}"
    chunks = build_chunks(md(text), "手册")
    parents = [c for c in chunks if c.is_parent]
    assert len(parents) >= 2
    assert all(len(p.content) <= settings.parent_fallback_tokens for p in parents)


def test_page_number_propagates():
    chunks = build_chunks([(3, "# A\n内容一"), (7, "# B\n内容二")], "P")
    by_path = {c.section_path: c.page for c in chunks}
    assert by_path.get("P > A") == 3 and by_path.get("P > B") == 7
