CREATE TABLE IF NOT EXISTS doc_chunk (
  id           BIGSERIAL PRIMARY KEY,
  doc_id       BIGINT       NOT NULL,
  parent_id    BIGINT,
  is_parent    BOOLEAN      NOT NULL DEFAULT false,
  content      TEXT         NOT NULL,
  embedding    vector(__EMBED_DIM__),
  section_path VARCHAR(512),
  page         INT,
  token_count  INT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_chunk_doc    ON doc_chunk(doc_id);
CREATE INDEX IF NOT EXISTS idx_chunk_parent ON doc_chunk(parent_id);
CREATE INDEX IF NOT EXISTS idx_chunk_hnsw   ON doc_chunk USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS llm_call (
  id            BIGSERIAL PRIMARY KEY,
  ts            TIMESTAMPTZ NOT NULL DEFAULT now(),
  session_id    BIGINT,
  message_id    BIGINT,
  node          VARCHAR(32) NOT NULL,
  model         VARCHAR(64) NOT NULL,
  prompt_id     VARCHAR(32),
  prompt_pack   VARCHAR(16),
  input_tokens  INT,
  output_tokens INT,
  latency_ms    INT,
  status        VARCHAR(16) NOT NULL,
  error_snippet VARCHAR(500)
);
CREATE INDEX IF NOT EXISTS idx_llm_call_msg ON llm_call(message_id);
CREATE INDEX IF NOT EXISTS idx_llm_call_ts  ON llm_call(ts);

ALTER TABLE doc_chunk ADD COLUMN IF NOT EXISTS document_version_id BIGINT;
CREATE INDEX IF NOT EXISTS idx_chunk_version ON doc_chunk(document_version_id);
ALTER TABLE document ADD COLUMN IF NOT EXISTS current_version_id BIGINT;

CREATE TABLE IF NOT EXISTS knowledge_space (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS document (
  id BIGSERIAL PRIMARY KEY,
  space_id TEXT NOT NULL,
  title TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS document_version (
  id BIGSERIAL PRIMARY KEY,
  document_id BIGINT NOT NULL,
  version INT NOT NULL,
  checksum CHAR(64) NOT NULL,
  storage_path TEXT NOT NULL,
  status TEXT NOT NULL,
  UNIQUE (document_id, version)
);

CREATE TABLE IF NOT EXISTS ingestion_job (
  id BIGSERIAL PRIMARY KEY,
  document_version_id BIGINT NOT NULL,
  status TEXT NOT NULL,
  attempts INT NOT NULL DEFAULT 0,
  lease_until TIMESTAMPTZ,
  last_error TEXT,
  next_retry_at TIMESTAMPTZ,
  UNIQUE (document_version_id)
);

CREATE TABLE IF NOT EXISTS knowledge_invocation (
  caller_id TEXT NOT NULL,
  invocation_id TEXT NOT NULL,
  request_hash CHAR(64) NOT NULL,
  status TEXT NOT NULL,
  result_json JSONB,
  safe_message TEXT,
  PRIMARY KEY (caller_id, invocation_id)
);
ALTER TABLE knowledge_invocation ADD COLUMN IF NOT EXISTS lease_owner TEXT;
ALTER TABLE knowledge_invocation ADD COLUMN IF NOT EXISTS lease_until TIMESTAMPTZ;
ALTER TABLE knowledge_invocation ADD COLUMN IF NOT EXISTS attempts INT NOT NULL DEFAULT 0;
ALTER TABLE knowledge_invocation ADD COLUMN IF NOT EXISTS fencing_token BIGINT NOT NULL DEFAULT 0;

-- 系统设置页的运行时配置覆盖(DESIGN §13)
CREATE TABLE IF NOT EXISTS system_config (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
