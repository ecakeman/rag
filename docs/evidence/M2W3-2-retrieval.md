# M2W3-2 检索管线 验收证据 — 2026-10-25 16:39:13
## git rev: fae60e6+工作区
## 过程修复: ① psycopg 向量参数需 CAST(::vector)(检索SQL+入库SQL); ② rank_bm25 负IDF 分不应被 <=0 过滤(改 ==0)

## ① pytest -q(新增 8 用例: RRF公式/上限、BM25中文命中/文档过滤、重排排序/降级、多查询开关、向量SQL真库过滤)
exit=0

## 结论: PASS(37 用例全绿;vector 腿在真实 PG 上验证含元数据过滤)
