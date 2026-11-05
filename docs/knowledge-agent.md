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

上传可以不带 `document_id`，这时创建文档和版本 1。带上已有文档时，该文档必须属于当前空间，版本号在锁行后递增。文件先写到临时路径，再原子改名。数据库事务失败会删除这次的文件。摄取成功之后才把 `current_version_id` 指到新版本。

摄取任务带 `lease_owner` 和 `fencing_token`。执行中每 30 秒续租。写块和完成都要匹配 owner 与 token。失去租约的 worker 不能覆盖新结果。

`message/send` 和管理接口都要求 `KNOWLEDGE_A2A_TOKEN`。Agent Card 的 GET 不要求 token。`topK` 必须在 1 到 32 之间，缺省为 8。空的 `knowledgeSpaceIds` 返回空结果。

这些行为没有在本轮启动服务或运行测试。
