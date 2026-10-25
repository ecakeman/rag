CREATE TABLE IF NOT EXISTS sys_user (
  id            BIGSERIAL PRIMARY KEY,
  username      VARCHAR(64)  NOT NULL UNIQUE,
  password_hash VARCHAR(100) NOT NULL,
  role          VARCHAR(16)  NOT NULL DEFAULT 'ADMIN',
  created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS system_config (
  "key"      VARCHAR(64)  NOT NULL PRIMARY KEY,
  value      TEXT         NOT NULL,
  updated_at TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS document (
  id          BIGSERIAL PRIMARY KEY,
  title       VARCHAR(256) NOT NULL,
  file_name   VARCHAR(256) NOT NULL,
  file_path   VARCHAR(512) NOT NULL,
  file_size   BIGINT       NOT NULL DEFAULT 0,
  mime_type   VARCHAR(128),
  status      VARCHAR(16)  NOT NULL DEFAULT 'UPLOADED',
  error_msg   TEXT,
  chunk_count INT          NOT NULL DEFAULT 0,
  created_by  BIGINT,
  created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_document_status ON document(status);

CREATE TABLE IF NOT EXISTS chat_session (
  id         BIGSERIAL PRIMARY KEY,
  title      VARCHAR(128) NOT NULL DEFAULT '新会话',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chat_message (
  id         BIGSERIAL PRIMARY KEY,
  session_id BIGINT      NOT NULL REFERENCES chat_session(id) ON DELETE CASCADE,
  role       VARCHAR(12) NOT NULL,
  content    TEXT        NOT NULL,
  citations  JSONB,
  trace      JSONB,
  latency_ms INT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_message_session ON chat_message(session_id);
