# M1W2-2 Python 摄入管线 验收证据 — 2026-10-25 15:57:54
## git rev: 827fd93+工作区

## ① pytest -q(容器内,修复 section_path 层级折叠后)
### exit=0
..................                                                       [100%]
18 passed in 0.66s
ai/tests/test_chunker.py:7
ai/tests/test_embedder.py:3
ai/tests/test_pipeline.py:3
ai/tests/test_api.py:5

## ② 真实链路: 上传→PROCESSING→解析→分块→embedding(无key 报错可观测)→FAILED 回调 —— 见 M1W2-1 证据 docId=14 与 llm_call 行
### 冒烟(真实 API)待 .devcontainer/.env 填入 LLM_API_KEY 后于 M2W4 补: 含向量维度断言 vector_dim=EMBED_DIM

## 结论: 单元/流程 18 用例全绿;正向含向量冒烟挂起到 key 就绪(计划内,非缺陷)
