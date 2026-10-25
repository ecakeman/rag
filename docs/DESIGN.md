# 企业内部文档智能检索系统 — 设计文档 v1.0

> 题目：《基于 SpringBoot+Vue 的 AI 问答知识库的企业内部文档智能检索系统》的设计与实现
> 本文档是实施的唯一依据。所有数值、命名、接口字段均为定稿，**照做即可，不再临场发挥**。任何修改必须更新 §14 变更记录并注明原因。
> 生成日期：2026-10-25。前序：环境搭建见 SETUP.md（已完成，提交 4ff20f6）。

---

## 目录

1. [目标与范围](#1-目标与范围)
2. [总体架构](#2-总体架构)
3. [技术选型定稿](#3-技术选型定稿)
4. [数据库设计（含完整 DDL）](#4-数据库设计)
5. [接口契约](#5-接口契约)
6. [系统侧（Java）详细设计](#6-系统侧java详细设计)
7. [AI 服务（Python）详细设计](#7-ai-服务python详细设计)
8. [Agent（LangGraph）详细设计](#8-agent-langgraph详细设计)
9. [前端详细设计](#9-前端详细设计)
10. [环境与工程（devcontainer 变更）](#10-环境与工程)
11. [模型与 Prompt 资产](#11-模型与-prompt-资产)
12. [评测方案（消融实验）](#12-评测方案)
13. [里程碑与任务分解](#13-里程碑与任务分解)
14. [风险与对策 / 决策记录 / 变更记录](#14-风险与对策--决策记录--变更记录)

---

## 1. 目标与范围

### 1.1 一句话目标

企业内部文档（制度/手册类）上传后自动构建知识库，用户以对话方式提问，系统通过 **agentic RAG**（路由→检索→重排→反思→引用式生成）给出**带出处、可溯源、拒绝编造**的回答。

### 1.2 范围内（做）

- 文档上传（pdf/docx/md/txt）、解析、标题感知切分、父子分段、向量化入库
- 混合检索（pgvector + BM25）+ 多查询扩展 + RRF + cross-encoder 重排 + 元数据过滤
- LangGraph agent：问题路由、多跳分解、检索反思循环、拒答兜底、落地校验
- 对话页：SSE 流式输出、reasoning trace 可视化、引用溯源侧栏
- 独立检索页（关键词+语义结果列表）
- JWT 登录（单角色 ADMIN）、文档管理页
- 消融评测 A0–A4，两套评测集，指标含召回/准确/引用准确率/延迟/成本

### 1.3 范围外（不做，写论文"展望"）

GraphRAG/知识图谱、表格多模态专检、OCR 扫描件、多角色细粒度权限、MinIO/OSS、模型本地化部署、移动端。

---

## 2. 总体架构

### 2.1 架构图

```
Vue3 (pure-admin-thin, Vite, :5173)
        │ HTTP /api/** + SSE
        ▼
SpringBoot 系统壳 (:8080)                FastAPI AI 服务 (:8000, 服务名 python)
  ├─ 认证(JWT)                            ├─ /ingest   摄入(异步任务+回调)
  ├─ 文档台账+状态机+文件落盘               ├─ /search   混合检索
  ├─ 会话/消息 CRUD                       ├─ /chat     SSE 问答(LangGraph)
  ├─ SSE 透传网关                          │    ├─ LlamaIndex: 解析/切分/检索管道
  ├─ 对 Python 的 HTTP 调用+对账           │    ├─ LangChain: 智谱/重排客户端
  └─ /internal/ingest/callback 接回调      │    └─ LangGraph: agent 编排
        │        │                                 │
        ▼        ▼                                 ▼
   PostgreSQL 16 + pgvector (服务名 db, :5432)
     ├─ Java 侧表: sys_user / document / chat_session / chat_message
     ├─ Python 侧表: doc_chunk (+LangGraph checkpointer 自建表)
     └─ 单库事务: chunk+向量同事务写入
```

### 2.2 铁律

1. 依赖单向：Vue→Java→Python。Python 永不调用 Java（回调是 Java 提供端点、Python 主动 POST，不算反向依赖业务逻辑）。
2. 两边按表归属访问 PG（§4.1），跨服务只认逻辑外键（存 id，不建 FK 约束）。
3. Java 不含任何 AI 逻辑；Python 不含用户/权限概念（不知道用户是谁，只收 sessionId）。
4. 全部数值参数集中在 `ai/app/config.py`（Python 侧）与 `backend/src/main/resources/application.yml`（Java 侧），代码中不许出现魔法数字。

### 2.3 仓库目录结构（定稿）

```
enterprise-doc-qa/
├── .devcontainer/
│   ├── devcontainer.json          # 追加 python 服务(见 §10)
│   ├── docker-compose.yml         # app + python + db(见 §10)
│   ├── post-create.sh
│   ├── maven-settings.xml
│   └── python/Dockerfile          # AI 服务镜像
├── backend/                       # SpringBoot 3.5 (已有骨架)
│   └── src/main/java/com/enterprise/docqa/
│       ├── BackendApplication.java
│       ├── common/                # R 响应体/异常/审计/JWT工具
│       ├── security/              # SecurityConfig, JwtFilter, AuthController
│       ├── document/              # Document{Entity,Repo,Service,Controller}, FileStorage
│       ├── ingestion/             # IngestClient(Java→Py), CallbackController, ReconcileJob
│       ├── chat/                  # Chat{Entity,Repo,Service,Controller}, SseGateway
│       └── search/                # SearchController(透传)
├── frontend/                      # pure-admin-thin 裁剪版(替换现有 vite 空骨架)
└── ai/                            # Python AI 服务
    ├── app/
    │   ├── main.py                # FastAPI 入口
    │   ├── config.py              # §7.1 全部常量
    │   ├── api/                   # ingest.py / chat.py / search.py
    │   ├── ingestion/             # convert.py(→Markdown) chunker.py embedder.py pipeline.py
    │   ├── retrieval/             # store.py(SQL向量) bm25.py fusion.py rerank.py
    │   ├── agent/                 # graph.py nodes.py prompts.py state.py tools.py
    │   └── db.py                  # engine/session
    ├── eval/                      # dataset 构建与评测脚本(§12)
    ├── requirements.txt
    └── tests/
```

---

## 3. 技术选型定稿

| 层 | 选型 | 版本锚点 |
|---|---|---|
| 前端 | Vue3 + TS + Vite + Element Plus + Pinia，模板 pure-admin-thin | vite 7/8 均可 |
| SSE 客户端 | @microsoft/fetch-event-source（支持 POST+header） | 最新 |
| 后端 | SpringBoot 3.5.0 + JPA + Validation + Lombok（骨架已建） | 3.5.0 锁定 |
| 后端追加依赖 | spring-boot-starter-security、jjwt 0.12.x、springdoc-openapi-starter-webmvc-ui 2.8.x、postgresql 驱动 | — |
| AI 服务 | Python 3.12 + FastAPI + uvicorn | — |
| 摄入/检索管道 | llama-index-core（MarkdownNodeParser、SentenceSplitter、QueryFusionRetriever、自定义 BaseRetriever） | ≥0.12 |
| 模型交互 | langchain-openai（ChatOpenAI 指向智谱兼容端点） | ≥0.3 |
| 编排 | langgraph + langgraph-checkpoint-postgres | ≥0.4 |
| 存储 | PostgreSQL 16 + pgvector（镜像 pgvector/pgvector:pg16，本机已缓存） | pgvector ≥0.7 |
| 向量 SQL | **手写 SQL**（psycopg + SQLAlchemy core），不用 LlamaIndex PGVectorStore（为承载父子块自建 schema，见 §7.3） | — |
| 中文分词/BM25 | jieba + llama-index BM25Retriever（rank_bm25 内核） | — |
| 文档转 Markdown | PDF→pymupdf4llm；DOCX→mammoth(convert_to_markdown)；MD/TXT 直读 | — |
| LLM(智谱) | glm-4-flash（路由/改写/评分/分解/校验）；生成用 GLM-4 系列主力（实施时以智谱控制台在售最新为准，记入 config 的 `SYNTH_MODEL`，默认填 `glm-4.5`，可一键改） | — |
| Embedding | 智谱 embedding-3，**dimensions=1024**（OpenAI 兼容端点） | — |
| Rerank | SiliconFlow `BAAI/bge-reranker-v2-m3`（POST /v1/rerank）；**失败自动降级为 RRF 顺序** | — |
| 端点 | 智谱兼容端点 `https://open.bigmodel.cn/api/paas/v4/`；SiliconFlow `https://api.siliconflow.cn/v1` | — |

---

## 4. 数据库设计

库：`doc_qa`；用户 `postgres`；密码 `root123`；容器内地址 `db:5432`。列名 snake_case。

### 4.1 表归属

| 表 | 归属（谁读写） | 谁建 |
|---|---|---|
| sys_user, document, chat_session, chat_message | Java | Java Flyway 式启动 SQL（`schema.sql`，`CREATE TABLE IF NOT EXISTS`） |
| doc_chunk | Python | 同一份 `ai/app/schema.sql`，服务启动时幂等执行 |
| langgraph checkpoint 表 | Python | langgraph-checkpoint-postgres 自动建，不手管 |

### 4.2 Java 侧 DDL（backend/src/main/resources/schema.sql）

```sql
CREATE TABLE IF NOT EXISTS sys_user (
  id            BIGSERIAL PRIMARY KEY,
  username      VARCHAR(64)  NOT NULL UNIQUE,
  password_hash VARCHAR(100) NOT NULL,            -- BCrypt
  role          VARCHAR(16)  NOT NULL DEFAULT 'ADMIN',
  created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS document (
  id          BIGSERIAL PRIMARY KEY,
  title       VARCHAR(256) NOT NULL,               -- 展示名(默认=文件名去后缀)
  file_name   VARCHAR(256) NOT NULL,
  file_path   VARCHAR(512) NOT NULL,               -- 相对仓库: data/files/{id}.{ext}
  file_size   BIGINT       NOT NULL DEFAULT 0,
  mime_type   VARCHAR(128),
  status      VARCHAR(16)  NOT NULL DEFAULT 'UPLOADED',
    -- UPLOADED→NOTIFIED→PROCESSING→READY / FAILED
  error_msg   TEXT,
  chunk_count INT          NOT NULL DEFAULT 0,     -- 子块数,回调时更新
  created_by  BIGINT,
  created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_document_status ON document(status);

CREATE TABLE IF NOT EXISTS chat_session (
  id         BIGSERIAL PRIMARY KEY,
  title      VARCHAR(128) NOT NULL DEFAULT '新会话', -- 首条用户消息前20字覆盖
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chat_message (
  id         BIGSERIAL PRIMARY KEY,
  session_id BIGINT      NOT NULL REFERENCES chat_session(id) ON DELETE CASCADE,
  role       VARCHAR(12) NOT NULL,                 -- user / assistant
  content    TEXT        NOT NULL,
  citations  JSONB,        -- [{no,chunkId,docId,docTitle,sectionPath,page,text}]
  trace      JSONB,        -- [{node,status,detail,tsMs}]
  latency_ms INT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_message_session ON chat_message(session_id);
```

种子用户：启动时 `CommandLineRunner` 检查空表则插入 `admin / admin123`（BCrypt）。

### 4.3 Python 侧 DDL（ai/app/schema.sql）

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS doc_chunk (
  id           BIGSERIAL PRIMARY KEY,
  doc_id       BIGINT       NOT NULL,              -- 逻辑外键→document.id(不建FK)
  parent_id    BIGINT,                             -- 父块id;父块自身为NULL
  is_parent    BOOLEAN      NOT NULL DEFAULT false,
  content      TEXT         NOT NULL,
  embedding    vector(1024),                       -- 仅子块非空;父块为NULL(不参与索引)
  section_path VARCHAR(512),                       -- "员工手册 > 假期 > 年假"
  page         INT,
  token_count  INT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_chunk_doc    ON doc_chunk(doc_id);
CREATE INDEX IF NOT EXISTS idx_chunk_parent ON doc_chunk(parent_id);
CREATE INDEX IF NOT EXISTS idx_chunk_hnsw   ON doc_chunk USING hnsw (embedding vector_cosine_ops);
```

**嵌入规则（定稿）**：只有子块生成 embedding；父块 embedding 恒 NULL。召回用子块，生成喂父块（small-to-big）。

### 4.4 状态机（document.status）

| 迁移 | 触发者 | 动作 |
|---|---|---|
| UPLOADED→NOTIFIED | Java | 文件落盘后 POST /ingest 成功返回 202 |
| NOTIFIED→PROCESSING | Java | 收到 Python 回调 status=PROCESSING（也可由 Python 首个回调直接给 READY，允许跳过） |
| PROCESSING→READY | Java | 收到回调 status=READY，更新 chunk_count |
| 任意→FAILED | Java | 收到回调 status=FAILED 或对账判定失败，记录 error_msg |
| NOTIFIED>5min 未变 | 对账 Job | 重发 /ingest（Python 按 docId 幂等） |
| PROCESSING>10min 未变 | 对账 Job | GET /ingest/{docId}/status 对账，仍无果→FAILED(error_msg="处理超时") |

---

## 5. 接口契约

约定：所有 HTTP 响应用统一响应体（§6.3）；字段命名一律 **camelCase**（Python 侧 DTO 用 pydantic alias_generator=to_camel）。时间用 epoch 毫秒。

### 5.1 前端 ↔ Java（全部需 JWT，除 /api/auth/login）

```
POST /api/auth/login            {username, password}            → {token, username}
POST /api/documents             multipart(file, title?)         → {id, status:"UPLOADED"}
GET  /api/documents?status=&page=1&size=10&q=                   → {total, records:[DocumentDTO]}
DELETE /api/documents/{id}                                       → {}   (先调 Python 清块,成功再删元数据+文件)
GET  /api/documents/{id}                                         → DocumentDTO
POST /api/chat/sessions         {title?}                        → {sessionId}
GET  /api/chat/sessions                                          → [{sessionId,title,createdAt}]
GET  /api/chat/sessions/{id}/messages                           → [MessageDTO] (时间正序)
POST /api/chat                  Accept: text/event-stream
       body {sessionId, message}
       → SSE 流(事件见 §5.3)          完成后 assistant 消息由 Java 落库
POST /api/search                {query, docIds?, topK?}         → {items:[SearchItem]}
GET  /api/files/{id}            下载原件(可选做)
POST /api/internal/ingest/callback   X-Internal-Token 头       → 204 (见 §5.2)
```

DocumentDTO：`{id, title, fileName, fileSize, status, errorMsg, chunkCount, createdAt}`

SearchItem：`{chunkId, docId, docTitle, sectionPath, page, text, score}`（score 保留 3 位小数）

### 5.2 Java ↔ Python（全部带 `X-Internal-Token`，值=环境变量 `INTERNAL_TOKEN`）

```
POST /ingest            {docId, filePath, fileName, title, callbackUrl}   → 202 {status:"QUEUED"}
GET  /ingest/{docId}/status                                            → {docId, status, chunkCount, errorMsg}
DELETE /ingest/{docId}                                                 → 204
POST /search            {query, docIds?, topK?}                         → {items:[SearchItem]}
POST /chat              {sessionId, message, history:[{role,content}]≤6}
                        Accept: text/event-stream → SSE 流(§5.3)
```

**回调（Python→Java）**：`POST {callbackUrl}` 即 `/api/internal/ingest/callback`
body：`{docId, status: "PROCESSING|READY|FAILED", chunkCount?, errorMsg?}` → Java 回 204。

### 5.3 SSE 事件协议（/chat，两段链路同构，Java 原样透传）

| event | data JSON | 说明 |
|---|---|---|
| `meta` | `{"sessionId":1,"userMessageId":10}` | 流开始 |
| `trace` | `{"node":"router","status":"start|end","detail":"SIMPLE","tsMs":...}` | agent 每节点起止；`detail` 为该节点结论摘要 |
| `token` | `{"text":"年假"}` | 答案增量，前端按序拼接 |
| `citations` | `{"items":[{no,chunkId,docId,docTitle,sectionPath,page,text}]}` | 答案完成后一次性下发 |
| `done` | `{"assistantMessageId":11,"latencyMs":8234}` | 流结束 |
| `error` | `{"code":5031,"message":"AI 服务不可用"}` | 任一错误，流终止 |

节点名固定枚举（trace 用）：`router, rewrite, retrieve, rerank, grade, sufficiency, decompose, synthesize, verify`。快路径只发 `router,retrieve,rerank,synthesize,verify`。

### 5.4 错误码

| code | 含义 |
|---|---|
| 0 | 成功 |
| 401/403/404/409/422 | 常规（未登录/无权/不存在/状态冲突/参数错） |
| 500 | 服务端异常 |
| 5031 | AI 服务不可达（Python 挂/超时） |
| 5032 | AI 服务内部错误（Python 返回 5xx 透传） |

---

## 6. 系统侧（Java）详细设计

### 6.1 认证

- Spring Security 6，无状态；放行 `/api/auth/login`、`/api/internal/**`（后者单独校验 `X-Internal-Token` 过滤器）。
- JWT：jjwt 0.12.x，HS256，密钥=环境变量 `JWT_SECRET`（dev 默认 `dev-jwt-secret-32bytes-minimum!!`），有效期 24h，claim 只放 `uid,username`。
- 密码 BCryptPasswordEncoder。初始用户 admin/admin123（§4.2）。

### 6.2 文档与摄入流程

```
上传(≤50MB, 后缀白名单 pdf/docx/md/txt)
 → 存 data/files/{id}.{ext}（相对 Java 工作目录）
 → INSERT document(UPLOADED)
 → RestClient POST http://python:8000/ingest (超时5s, 失败重试2次)
     成功→status=NOTIFIED；最终失败→FAILED(error_msg="通知AI服务失败")
 → 等 Python 回调更新状态
删除: DELETE /ingest/{docId}(Python 删 chunk) 成功 → 删元数据+文件; Python 不可用→409
```

对账 Job（`@Scheduled(fixedDelay=60s)`）：按 §4.4 后两条规则处理。

### 6.3 全局约定

- 响应体 `R<T>`：`{code:0, message:"ok", data:T}`；全局 `@RestControllerAdvice` 统一异常→R。
- 参数校验用 jakarta validation + `@Valid`，校验失败→422。
- 所有实体 `created_at/updated_at` 由 JPA Auditing 维护。
- springdoc：路径 `/swagger-ui.html`，仅 dev profile 开放。
- CORS：dev 允许 `http://localhost:5173`。

### 6.4 SSE 透传网关（关键实现，约 50 行，禁止引 WebFlux）

```
POST /api/chat
 → 校验 session；INSERT user 消息；返回 SseEmitter(timeout=120s)
 → 线程池提交: JDK HttpClient 发 POST /chat(读 SSE 流, 按行解析 event/data)
    event=token/trace/meta/citations/done → emitter.send 同构事件
    event=done: 收集全文+citations+trace+latency → INSERT assistant 消息
    event=error 或 IO 异常 → emitter.send(error事件) 后 complete
 → Python 连接超时 10s；读空闲超时 90s
```

### 6.5 配置（application.yml 关键项）

```yaml
spring:
  datasource:
    url: jdbc:postgresql://${DB_HOST:db}:5432/doc_qa
    username: postgres
    password: ${DB_PASSWORD:root123}
  servlet.multipart.max-file-size: 50MB
ai:
  base-url: http://${AI_HOST:python}:8000
  internal-token: ${INTERNAL_TOKEN:dev-doc-qa-internal-token}
  ingest-timeout: 5s
app:
  jwt-secret: ${JWT_SECRET:dev-jwt-secret-32bytes-minimum!!}
  jwt-ttl: 24h
  file-dir: data/files
```

---

## 7. AI 服务（Python）详细设计

### 7.1 config.py（全部常量，单一事实来源）

```python
# 摄入
CHILD_TOKENS=256; OVERLAP_TOKENS=40; PARENT_FALLBACK_TOKENS=768; EMBED_BATCH=64
# 检索
MULTI_QUERY_N=3            # 原query+3变体
TOP_K_PER_LEG=8; FUSION_TOP_K=10; RERANK_TOP_N=5; RRF_K=60
BM25_INIT_ON_STARTUP=True  # 启动时全量重建BM25,增量在ingest后更新
# agent
GRADE_THRESHOLD=6; MAX_HOPS=3; TEMPERATURE_FAST=0.1; TEMPERATURE_SYNTH=0.3
FAST_MODEL="glm-4-flash"; SYNTH_MODEL="glm-4.5"   # SYNTH 实施时按控制台在售主力改
# 超时/重试
LLM_TIMEOUT_FAST=15; LLM_TIMEOUT_SYNTH=60
RERANK_TIMEOUT=5           # 超时/失败→降级用RRF顺序,不报错
EMBED_DIM=1024
# 消融开关(§12)
ENABLE_HYBRID=True; ENABLE_MULTIQUERY=True; ENABLE_RERANK=True; ENABLE_AGENT=True
# 端点/密钥 从环境变量: ZHIPU_API_KEY, SILICONFLOW_API_KEY, INTERNAL_TOKEN,
#   DATABASE_URL=postgresql+psycopg://postgres:root123@db:5432/doc_qa
```

### 7.2 摄入管线（POST /ingest → 异步 → 回调）

```
1. 收到请求: 202 QUEUED; 若该 docId 已有 chunk → 先 DELETE(幂等重摄入)
2. 后台任务(FastAPI BackgroundTasks):
   a. 回调 PROCESSING
   b. 转 Markdown: pdf→pymupdf4llm; docx→mammoth; md/txt 直读
      记录每个片段的页码(pdf: pymupdf4llm 保留 page 信息; 无页码则 None)
   c. 切分(见 7.2.1)
   d. 子块批量 embedding(BATCH=64, 失败重试2次, 仍失败→回调 FAILED)
   e. 单事务写入 doc_chunk(先 DELETE doc_id=? 再 INSERT 全量)
   f. 回调 READY{chunkCount=子块数} ; BM25 索引增量更新
   g. 任一步异常 → 回调 FAILED{errorMsg=str(e)[:500]}
```

**7.2.1 切分算法（定稿）**

```
输入: Markdown 文本
1. llama-index MarkdownNodeParser 按标题层级切 section
   → 每个 section = 父块(is_parent=true, embedding=NULL,
      section_path="文档标题 > H1 > H2"(按层级拼接), page=section 首页码)
2. section 内 SentenceSplitter(chunk_size=CHILD_TOKENS, overlap=OVERLAP_TOKENS)
   → 子块(parent_id=父块id, embedding=向量)
3. 退化规则: 文档无任何标题(md 直转的txt/部分pdf) → 按 PARENT_FALLBACK_TOKENS
   滑窗(无重叠)当父块, 再按规则2切子块
4. 表格线性化: markdown 表格每行转 "列名1:值1; 列名2:值2" 纯文本行
5. 超长单 section(>2000 token)按 PARENT_FALLBACK_TOKENS 再切为多个父块
```

### 7.3 检索管线（/search 与 agent 的 retrieve 工具共用）

```
query(可选: 先经 agent 改写)
 ├─ ENABLE_MULTIQUERY: LlamaIndex QueryFusionRetriever(LLM=Flash) 生成 3 变体
 │    否则单 query
 ├─ 双腿召回(每腿 TOP_K_PER_LEG=8):
 │    向量腿: 手写SQL  SELECT id,parent_id,content,section_path,page,
 │            1 - (embedding <=> :qvec) AS score
 │            FROM doc_chunk WHERE embedding IS NOT NULL
 │              [AND doc_id = ANY(:docIds)]          -- 元数据过滤
 │            ORDER BY embedding <=> :qvec LIMIT 8
 │    关键词腿: BM25Retriever(jieba 分词, 内存索引, 启动时全量+ingest增量)
 ├─ 融合: RRF  score(d)=Σ_legs 1/(RRF_K + rank_leg(d))  取 FUSION_TOP_K=10
 │    ENABLE_HYBRID=False 时: 仅向量腿,按余弦分排序(消融A0/A1差异)
 └─ 重排(ENABLE_RERANK): SiliconFlow /v1/rerank{model=BAAI/bge-reranker-v2-m3,
      query, documents=[10块文本]} → 取 RERANK_TOP_N=5
      失败/超时 → 降级: 直接用 RRF 序前5(记 trace detail="rerank:degraded")
输出: 子块列表(含score) → 需要父块时 SELECT * WHERE id IN (parent_ids)
```

### 7.4 /chat 与 LangGraph 的关系

`POST /chat` = 构建 LangGraph 入口 state → `graph.astream(..., stream_mode="updates")` → 把节点事件映射为 §5.3 的 `trace` 事件；`synthesize` 节点内部用 token 流回调推送 `token` 事件。checkpoint：`AsyncPostgresSaver`（连接串同 DATABASE_URL），`thread_id=str(sessionId)`。

---

## 8. Agent（LangGraph）详细设计

### 8.1 状态 schema（state.py）

```python
class AgentState(TypedDict):
    session_id: int
    question: str            # 当前要回答的原始问题
    standalone_query: str    # 改写后独立问题
    qtype: str               # SIMPLE | COMPLEX | CHITCHAT
    sub_questions: list[str] # COMPLEX 的子问题(≤3)
    hop: int                 # 当前跳数
    hits: list[dict]         # 累计相关块[{chunkId,text,sectionPath,docId,page,score}]
    new_hit_count: int       # 本跳新增相关块数
    verdict: str             # ENOUGH | NEED_MORE | REFUSE
    answer: str
    citations: list[dict]
    verified: str            # PASS | FAIL
```

### 8.2 节点与边（graph.py）

```
START → rewrite → router
router ─ CHITCHAT → synthesize(无资料模式) → END
router ─ SIMPLE   → retrieve → rerank → grade → synthesize → verify → END
router ─ COMPLEX  → decompose → retrieve → rerank → grade → sufficiency
   sufficiency ─ NEED_MORE 且 hop<MAX_HOPS 且 上跳 new_hit_count>0 → (hop+1) retrieve
   sufficiency ─ ENOUGH 或 hop≥3 或 new_hit_count=0 → synthesize → verify → END
verify ─ PASS → END
verify ─ FAIL → synthesize(重试1次, 附"务必仅依据资料") → END(仍FAIL则答案尾部加声明)
检索零相关(grade 后 hits 空) → synthesize 走拒答模板 → END
```

消融 `ENABLE_AGENT=False`：跳过 router/decompose/sufficiency/verify，固定单跳 SIMPLE 路径（A0–A3 配置用）。

### 8.3 节点实现要点

| 节点 | 模型 | 温度 | 超时 | 说明 |
|---|---|---|---|---|
| rewrite | Flash | 0.1 | 15s | history+question→独立问题；history 空则原样 |
| router | Flash | 0.1 | 15s | 输出 JSON，解析失败→默认 SIMPLE（宁快勿卡） |
| decompose | Flash | 0.1 | 15s | ≤3 子问题；每跳取 queue[hopt] 作为本跳 query |
| retrieve | — | — | 10s | §7.3 管线，本跳 query=子问题或 standalone_query |
| rerank | — | — | 5s | §7.3 |
| grade | Flash | 0.1 | 15s | 逐块 0-10 分；score≥6 判相关；只把相关块并进 hits（按 chunkId 去重） |
| sufficiency | Flash | 0.1 | 15s | ENOUGH/NEED_MORE+missing 描述；NEED_MORE 时下跳 query=missing+已有信息改写 |
| synthesize | 主力 | 0.3 | 60s | 输入=去重后 top 相关块（**子块命中→喂父块**，按 score 截前 8 块）；token 流式 |
| verify | Flash | 0.1 | 15s | PASS/FAIL+未支撑句 |

**引用编号规则**：synthesize 的资料按输入顺序编号 1..n，模型文本中 `[n]` 对应；Python 将编号映射回 chunkId/父块信息生成 citations。生成文本若含未定义编号 → 该引用丢弃并在 trace 记 warning。

**拒答模板**（hits 为空时 synthesize 直接输出，不调 LLM）：
`根据现有知识库资料，无法回答该问题。建议：1) 更换问法 2) 上传相关文档后再试。`

---

## 9. 前端详细设计

### 9.1 模板引入（替换现有 frontend/）

```
1. git clone --depth 1 https://github.com/pure-admin/vue-pure-admin-thin frontend-new
   (网络差走 ghproxy 镜像, 或 Windows 侧下载后拷入)
2. 裁剪: 保留 src/{layout,router,store,api,views/login,directives,utils}, package.json 核心依赖
3. 删除 demo 路由/页面; vite.config.ts: server.host=true(保留), 加 proxy:
     "/api": {target: "http://localhost:8080", changeOrigin: true}
4. 追加依赖: @microsoft/fetch-event-source
5. 路由(定稿3页):
   /login           → 模板自带(改调 /api/auth/login, 存 token 到 pinia)
   /docs            → 文档管理
   /chat            → 对话(默认首页)
   /search          → 检索
```

### 9.2 页面规格

**文档管理 /docs**：El-Table（标题/文件名/大小/状态 Tag/块数/时间/操作）；上传按钮（el-upload，白名单+50MB 校验）；状态列：UPLOADED/NOTIFIED/PROCESSING 显示加载态，行内 3s 轮询（仅对未终态行），READY→绿，FAILED→红+error_msg tooltip；删除二次确认。

**对话 /chat**：左会话列表（新建/删除/切换）；主区消息气泡；**答案区流式渲染**（token 拼接）；气泡下方引用角标 [1][2]，点击→右侧抽屉显示原文+文档标题+章节路径+页码；**顶部折叠面板 "思考过程"**：按 trace 事件实时追加节点条目（节点名+detail+耗时），父级折叠默认收起；底部输入框 Enter 发送（Shift+Enter 换行），发送中禁用。

**检索 /search**：搜索框+可选文档范围多选；结果列表（docTitle/sectionPath/页码/文本，查询词 mark 高亮），显示 score。

### 9.3 SSE 客户端

`fetchEventSource('/api/chat', {method:'POST', headers:{Authorization}, body, onmessage(e){按 event 分发}})`；`error` 事件→ElMessage 报错；`done`→停止拼接。

---

## 10. 环境与工程

### 10.1 docker-compose.yml（定稿全文，替换 MySQL 版）

```yaml
services:
  app:
    image: mcr.microsoft.com/devcontainers/java:21
    command: sleep infinity
    volumes:
      - ..:/workspaces/enterprise-doc-qa:cached
    depends_on:
      db: {condition: service_healthy}
      python: {condition: service_started}

  python:
    build: ./python
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    environment:
      ZHIPU_API_KEY: ${ZHIPU_API_KEY}
      SILICONFLOW_API_KEY: ${SILICONFLOW_API_KEY}
      INTERNAL_TOKEN: ${INTERNAL_TOKEN:-dev-doc-qa-internal-token}
      DATABASE_URL: postgresql+psycopg://postgres:root123@db:5432/doc_qa
    volumes:
      - ..:/workspaces/enterprise-doc-qa:cached
    depends_on:
      db: {condition: service_healthy}
    restart: unless-stopped

  db:
    image: pgvector/pgvector:pg16
    restart: unless-stopped
    environment:
      POSTGRES_PASSWORD: root123
      POSTGRES_DB: doc_qa
      TZ: Asia/Shanghai
    ports:
      - "5432:5432"        # 实施时实测宿主占用; 被占改 15432:5432 并记入 §14
    volumes:
      - pg-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d doc_qa"]
      interval: 5s
      timeout: 3s
      retries: 30

volumes:
  pg-data:
```

devcontainer.json：`"service": "app"` 不变，features 不变（node+java/maven）；post-create.sh 不变。MySQL 容器与卷由 `docker compose down -v`（旧 project enterprise-doc-qa_devcontainer）清除。backend pom：`mysql-connector-j`→`org.postgresql:postgresql`(runtime)。

### 10.2 .devcontainer/python/Dockerfile

```dockerfile
FROM python:3.12-slim
WORKDIR /workspaces/enterprise-doc-qa/ai
ENV PYTHONUNBUFFERED=1 PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
EXPOSE 8000
```

### 10.3 requirements.txt（主版本锁 minors）

```
fastapi>=0.115
uvicorn[standard]>=0.30
pydantic>=2.7
pydantic-settings>=2.2
httpx>=0.27
sqlalchemy>=2.0
psycopg[binary]>=3.1
llama-index-core>=0.12
llama-index-readers-file>=0.4
llama-index-embeddings-openai>=0.3
langchain-core>=0.3
langchain-openai>=0.3
langgraph>=0.4
langgraph-checkpoint-postgres>=2.0
rank-bm25>=0.2.2
jieba>=0.42
pymupdf4llm>=0.0.17
mammoth>=1.6
tenacity>=8.3
```

### 10.4 端口与凭据总表

| 项 | 值 |
|---|---|
| 前端 dev | 5173 |
| Java | 8080（容器内外一致，IDE 转发） |
| Python | 8000（仅 compose 网内，不发布宿主） |
| PostgreSQL | 容器内 5432；宿主映射 5432（被占→15432，见 §10.1 注） |
| DB 凭据 | postgres / root123 / 库 doc_qa |
| 种子账号 | admin / admin123 |
| 内部 token | dev 环境统一 `dev-doc-qa-internal-token`（env `INTERNAL_TOKEN`） |
| 密钥 | ZHIPU_API_KEY、SILICONFLOW_API_KEY 放 `.devcontainer/.env`（git 忽略，模板 `.env.example` 提交） |

### 10.5 运维备忘（本机已知坑）

- WSL 偶发重启导致容器 255 退出：db/python 已有 restart 策略；app 容器执行 `docker update --restart unless-stopped enterprise-doc-qa_devcontainer-app-1`。
- `.gitignore` 追加：`data/files/`、`.devcontainer/.env`、`ai/__pycache__/`、`*.pyc`。
- pip/npm/maven 均已走国内源（post-create + Dockerfile PIP_INDEX_URL + 阿里云 settings.xml）。

---

## 11. 模型与 Prompt 资产

### 11.1 模型分工

| 用途 | 模型 | 温度 | 备注 |
|---|---|---|---|
| rewrite/router/decompose/grade/sufficiency/verify | glm-4-flash | 0.1 | 便宜+快 |
| synthesize | SYNTH_MODEL(默认 glm-4.5) | 0.3 | 实施时锁定在售主力 |
| embedding | embedding-3 | — | dimensions=1024 |
| rerank | bge-reranker-v2-m3(SiliconFlow) | — | 失败降级 RRF |
| LLM-judge(评测) | SYNTH_MODEL | 0.0 | 独立会话,≠生成实例 |

### 11.2 Prompt 全文（存 ai/app/agent/prompts.py，占位符 `{}` 由代码填充）

**P1 rewrite**
```
你是查询改写器。根据【对话历史】把【当前问题】改写为不依赖上下文、可独立检索的完整问题。
【对话历史】{history}
【当前问题】{question}
仅输出 JSON: {"query": "改写后的问题"}
```

**P2 router**
```
你是企业知识库问答系统的问题路由器。判断问题类型:
SIMPLE=单一事实/条款查询,一次检索即可回答(例:年假有几天?)
COMPLEX=需跨文档综合/多步推理/比较(例:工作满3年与满5年的年假差几天?报销流程和审批人是谁?)
CHITCHAT=问候闲聊,与企业知识无关
【问题】{question}
仅输出 JSON: {"type":"SIMPLE|COMPLEX|CHITCHAT","reason":"一句话"}
```

**P3 decompose**
```
把【问题】拆成至多3个可独立检索的子问题,按求解顺序排列。只拆真正需要多次检索的问题。
【问题】{question}
仅输出 JSON: {"subQuestions": ["...", "..."]}
```

**P4 grade**
```
你是检索片段相关性评分器。【问题】与【片段】的相关度打分:
0-2无关;3-5弱相关;6-8相关可作依据;9-10直接命中。
【问题】{question}
【片段】{chunk}
仅输出 JSON: {"score":0-10整数,"reason":"一句话"}
```

**P5 sufficiency**
```
判断【已收集的相关片段】是否足以完整回答【问题】。若不足,指出缺什么(将用于生成下一跳检索词)。
【问题】{question}
【已收集片段摘要】{hits_summary}
仅输出 JSON: {"verdict":"ENOUGH|NEED_MORE","missing":"缺少的信息,ENOUGH时为空串"}
```

**P6 synthesize**
```
你是企业内部知识库助手。严格依据【资料】回答【问题】,规则:
1)每个论点后标注资料编号,如[1];只能引用资料中存在的编号;
2)资料未涵盖的内容,回答"根据现有资料无法回答该问题",禁止编造;
3)先结论后依据,简体中文,条理清晰;
4)资料中如有数字/条件(年限/金额/天数),必须原样引用不得改算。
【资料】
{numbered_chunks}
【问题】{question}
```

**P7 verify**
```
你是答案审核员。逐句检查【回答】是否被【资料】支撑。
仅输出 JSON: {"verdict":"PASS|FAIL","unsupported":"无依据的句子,多个用分号;PASS时为空串"}
```

**P8 拒答**（代码模板，不调模型）：见 §8.3。

### 11.3 输出解析约定

Flash 系输出统一按 JSON 解析：剥掉 markdown 代码围栏→`json.loads`；解析失败重试 1 次；再失败用节点各自的降级默认值（router→SIMPLE、grade→score 5、sufficiency→ENOUGH、verify→PASS），并在 trace 中记 `detail="parse-fallback"`。

---

## 12. 评测方案

### 12.1 消融配置（config 开关矩阵）

| 配置 | ENABLE_HYBRID | ENABLE_MULTIQUERY | ENABLE_RERANK | ENABLE_AGENT |
|---|---|---|---|---|
| A0 朴素RAG | false | false | false | false |
| A1 +混合RRF | true | false | false | false |
| A2 +多查询 | true | true | false | false |
| A3 +重排 | true | true | true | false |
| A4 完整agentic | true | true | true | true |

### 12.2 数据集（eval/datasets/）

- 语料：公开味企业文档（员工手册、考勤制度、报销制度、产品说明等，10–20 份，pdf/docx/md 混合，总块数 ≥1000）。
- `simple_qa.csv`：30 条单跳事实题（字段：`id,question,ref_answer,doc_ids,type=simple`）。
- `multi_hop_qa.csv`：30 条跨文档/推理题（字段同上，`type=multi_hop`）。
- 人工出题+人工标注参考答案与出处文档；每条必须有唯一可验证答案。

### 12.3 指标与公式

| 指标 | 定义 |
|---|---|
| Recall@5 / @10 | 命中出处文档的 chunk 出现在检索前 k 的题数占比 |
| MRR | 首个相关 chunk 排名倒数的平均 |
| 答案准确率 | LLM-judge(P9 rubric: 完全正确/部分/错误) 判"完全正确"占比 + 20% 人工抽检复核 |
| 引用准确率 | 被判定支撑回答的引用数 / 总引用数 |
| 延迟 | P50/P95（前端 done 事件 latencyMs） |
| 成本 | 每题 LLM 调用次数、token 消耗（智谱控制台导出） |

**P9 judge prompt**
```
你是阅卷员。依据【参考答案】判定【系统回答】:full=完全正确/partial=部分正确/wrong=错误。
判 full 要求:关键事实全部一致;数值/条件不得有差。
仅输出 JSON: {"grade":"full|partial|wrong","reason":"一句话"}
```

### 12.4 流程与产出

`python -m eval.run --config A0..A4 --dataset all --out results/`：逐题调用 /chat（关流式聚合），解析 citations 与 trace 统计跳数/降级次数；产出 `results/{config}.csv`（逐题）与 `summary.md`（均值表）。同一数据集每个配置跑 1 次（温度≥0.1 的节点对同输入有波动，记录并在论文说明；如需方差可 `--repeat 3` 取均值）。

---

## 13. 里程碑与任务分解

| # | 周 | 任务 | 验收标准 |
|---|---|---|---|
| M1 | W1(11.3前) | D5 环境变更(§10)：换PG、加python服务、pom/yml 切换 | compose up 三服务 healthy；psql 连通；/ping 200 |
| M1 | W1 | Java 骨架：security+JWT+R+异常+swagger+seed 用户 | 登录换 token；swagger 可见全部接口 |
| M1 | W2(11.15前) | 文档模块+文件落盘+IngestClient+Callback+对账 | 上传pdf→状态机走通→READY/FAILED 正确；重发幂等 |
| M1 | W2 | Python 骨架：FastAPI+/ingest 全管线(§7.2)+schema | 上传→doc_chunk 有父子块与向量；回调到达 |
| M1 | W2 | 前端：模板裁剪+登录+文档页 | 三状态可见、轮询、删除闭环 |
| M2 | W3(11.29前) | 检索管线：向量腿+BM25+RRF+多查询+重排+元数据过滤 | /search 返回带 score；rerank 降级演练通过 |
| M2 | W4(12.6前) | 朴素问答链路(A0)：SSE 透传+token 流+citations 落库 | 对话页 A0 可用；trace/引用齐 |
| M2 | W4 | 评测脚手架+语料 v1+simple 集 30 条 | `eval.run --config A0` 出 CSV |
| M3 | W5-6(12.20前) | LangGraph：state/节点/边/终止/拒答/降级+checkpointer | 多跳题演示题正确走 2 跳；中断恢复演示 |
| M3 | W6 | trace 可视化+对话页打磨 | 前端实时显示节点流；引用抽屉可用 → **中期演示** |
| M4 | W7-10(1.24前) | multi_hop 集 30 条；A0-A4 全量跑通；修问题 | summary.md 五配置齐全 |
| M4 | W10 | 检索页+边界打磨+README | 全流程无断点；假重启不丢数据 |
| M5 | W11-16(3.7前) | 补实验(分块消融 256/512 可选)+论文初稿 | 实验章数据表齐 |
| M5 | W16-20(4.30前) | 论文定稿+答辩演示脚本+预演 | — |

每周结束：代码合 main 一次；评测结果 CSV 不入 git（results/ 忽略）。

---

## 14. 风险与对策 / 决策记录 / 变更记录

### 14.1 风险

| 风险 | 对策（已内建） |
|---|---|
| 智谱兼容端点不支持 embedding dimensions=1024 | 实施第一步先 curl 验证；不支持→全库改 2048，只动 EMBED_DIM 与 DDL，代码不变 |
| SiliconFlow 欠费/不可达 | rerank 5s 超时自动降级 RRF 序（§7.3） |
| agent 循环空转 | MAX_HOPS=3 + 连续零新增终止（§8.2） |
| Flash JSON 输出不稳定 | 剥围栏+重试1次+节点级降级默认值（§11.3） |
| PDF 无文本层/乱码 | ingest 报 FAILED 提示换源文件；OCR 在展望 |
| PG 宿主 5432 被占 | 改 15432 映射，容器内不变 |
| WSL 重启容器退 | restart 策略+§10.5 手册 |

### 14.2 决策记录（定稿，不再重议）

| # | 决策 | 被否方案 | 理由 |
|---|---|---|---|
| 1 | Java 壳+Python AI 双服务 | 全 Java/全 Python | 题目保真；生态对口 |
| 2 | LangGraph 编排 | LlamaIndex Workflows/纯手写循环 | 图显式可控；工业主流；答辩可讲 |
| 3 | PG+pgvector 单库 | MySQL+Chroma | 事务一致；checkpoint 同库；镜像本机已有 |
| 4 | 父子分段 small-to-big | 纯平铺切块 | Dify 验证的成熟答案 |
| 5 | BM25 进程内(jieba) | PG zhparser | 镜像无该扩展；规模无所谓 |
| 6 | 向量 SQL 手写 | LlamaIndex PGVectorStore | 自定义父子 schema |
| 7 | SiliconFlow cross-encoder 重排 | 纯智谱 LLM rerank | 效果/成本优；降级路径保底 |
| 8 | GraphRAG 不做 | — | 构建贵；agent 分解已覆盖多跳 |
| 9 | 前端 pure-admin-thin | vben | Element Plus 生态+thin 无 demo 负担 |
| 10 | JPA | MyBatis-Plus | 骨架已含；表少 |

### 14.3 变更记录

| 日期 | 版本 | 内容 |
|---|---|---|
| 2026-10-25 | v1.0 | 首版定稿（本文档） |
