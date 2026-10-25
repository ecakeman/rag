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

-- 系统设置页的运行时配置覆盖(DESIGN §13)
CREATE TABLE IF NOT EXISTS system_config (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
