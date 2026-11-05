# Knowledge Agent 运行模式

同一份 Python 代码有两种启动方式，由 `KNOWLEDGE_AGENT_MODE` 决定。默认是 `false`。

## Legacy RAG

开发容器继续连接 `doc_qa`，不设置 `KNOWLEDGE_AGENT_MODE`。

- 初始化 `ai/app/schema.sql`：`doc_chunk`、`llm_call`、`system_config`。
- 不修改原 Backend 的 `document` 表，不加 `current_version_id`。
- 挂载 `/ingest`、`/search`、`/chat`。
- `/ingest` 的请求仍然是 `docId`、`filePath`、`fileName`、`title`、`callbackUrl`。它按 `doc_id` 替换块，不接收也不编造 `document_version_id`。
- BM25 只从 `doc_chunk` 装载子块。

## Knowledge Agent

AlertFlow 把 `KNOWLEDGE_AGENT_MODE=true`，并使用单独的 `knowledge` 数据库。

- 初始化 `ai/app/schema_knowledge.sql`。表是 `knowledge_space`、`document`、`document_version`、`doc_chunk`、`ingestion_job`、`knowledge_invocation`。
- `document` 带 `space_id` 和 `current_version_id`。`doc_chunk` 带 `document_version_id`。
- 只挂载 `/health`、A2A 和 `/spaces/{space_id}/documents`、`/jobs/{job_id}`。
- Schema 初始化失败时 `/health` 返回 503。
- 检索只返回原文片段和来源。不生成回答、摘要或诊断结论。

上传可以不带 `document_id`，这时创建文档和版本 1。带上已有文档时，该文档必须属于当前空间，版本号在锁行后递增。文件按 1MiB 分块写入临时路径，同时计算 SHA-256。`KNOWLEDGE_UPLOAD_MAX_BYTES` 默认 33554432，必须是正数，超过后返回 413 并删除临时文件。`KNOWLEDGE_INGEST_MAX_ATTEMPTS` 默认 5。这两个值必须是正数，否则进程在加载配置时失败。数据库事务失败会删除这次的最终文件。摄取成功之后才把 `current_version_id` 指到新版本。

超过 24 小时、且 `document_version.storage_path` 没有引用的上传文件，由摄取循环清理。清理只看 `KNOWLEDGE_STORAGE_ROOT`。

摄取任务带 `lease_owner` 和 `fencing_token`。执行中每 30 秒续租。写块、完成和失败都要匹配 owner、token、`PROCESSING` 和仍有效的租约。`attempts` 在每次领取并开始处理时加一。`KNOWLEDGE_INGEST_MAX_ATTEMPTS` 默认 5。未达上限时回到 PENDING，30 秒后重试。达到上限，或 Worker 退出后租约过期，Job 和对应的非 READY 版本改为 FAILED，不修改 `current_version_id`。

BM25 是进程内索引。数据库提交成功后才刷新。刷新失败只记日志，Job 保持 READY，摄取循环每 30 秒再试。进程启动时也会从当前 READY 版本重建。

`message/send` 和管理接口都要求 `KNOWLEDGE_A2A_TOKEN`。Agent Card 的 GET 不要求 token。`topK` 必须在 1 到 32 之间，缺省为 8。空的 `knowledgeSpaceIds` 返回空结果。

这些行为只做了代码阅读，没有在本轮启动服务或运行测试。
