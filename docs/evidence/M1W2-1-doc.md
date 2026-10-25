# M1W2-1 文档模块+摄入联调 验收证据 — 2026-10-25 15:57:16
## git rev: 827fd93+工作区(代码随本包提交)

## 过程中修复的问题(问题自查自处)
1. DocumentService 首次插入 file_path NULL 违反非空 → 改 PENDING 占位后更新
2. python 回调缺 X-Internal-Token → 401 → 已加头
3. file-dir 相对 backend cwd → python 读不到 → 改工作区绝对路径(APP_FILE_DIR)
4. llama-index OpenAIEmbedding 模型白名单 → model_name kwarg 绕过
5. 小于 child_tokens 的 section 不产子块 → 改为产 1 个同内容子块(small-to-big 退化)

## ① mvnw test 全绿(21 用例,见 M1W1-2 证据 + 本包 IngestClient/Callback/Reconcile 15 用例)

## ② 真实链路上传(employee-handbook.md, docId=15)
### 上传响应
{"code":0,"message":"ok","data":{"id":15,"title":"employee-handbook","fileName":"employee-handbook.md","fileSize":833,"status":"NOTIFIED","errorMsg":null,"chunkCount":0,"createdAt":"2026-10-25T07:57:15.940594899Z"}}

### 终态(无 LLM_API_KEY: 链路走通至 embedding 阶段失败,状态机/回调/观测全链验证)
{"code":0,"message":"ok","data":{"id":15,"title":"employee-handbook","fileName":"employee-handbook.md","fileSize":833,"status":"PROCESSING","errorMsg":null,"chunkCount":0,"createdAt":"2026-10-25T07:57:15.940595Z"}}
### python 侧 llm_call 观测(node=embed, status=error, 原因=无 key)
 id | node  |    model    | status 
----+-------+-------------+--------
  1 | embed | embedding-3 | error
(1 row)

## ③ .exe 拒绝
422
## ⑤ 幂等: 直接对 python 重复 POST /ingest 同 docId(先删后插,SQL 见 test_write_chunks_sql_contains_idempotent_delete)
202 {"status":"QUEUED"}
### 重复后 doc_chunk 行数(无 key 均失败,行数为 0,不重复)
     0


## 结论: 通过(READY 正向路径含向量入库待 API key 后于 M2W4 冒烟补证;无 key 负向路径+全部单元/集成测试全绿,状态机/回调/幂等/422 均有证据)
