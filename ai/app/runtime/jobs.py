"""摄取任务租约。进程重启后可以接管过期任务。"""
from __future__ import annotations

import threading
import time
from pathlib import Path

from sqlalchemy import text

from app.db import engine
from app.ingestion.pipeline import run_ingest


def claim_once() -> bool:
    with engine.begin() as conn:
        row = conn.execute(text("""
            UPDATE ingestion_job
            SET status='PROCESSING', attempts=attempts+1, lease_until=now() + interval '2 minutes'
            WHERE id = (
                SELECT id FROM ingestion_job
                WHERE status IN ('PENDING','PROCESSING')
                  AND (lease_until IS NULL OR lease_until < now())
                  AND (next_retry_at IS NULL OR next_retry_at <= now())
                ORDER BY id
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING id, document_version_id
        """)).fetchone()
    if row is None:
        return False
    job_id, version_id = row
    try:
        with engine.connect() as conn:
            version = conn.execute(text("""
                SELECT dv.id, dv.document_id, dv.storage_path, d.title
                FROM document_version dv JOIN document d ON d.id=dv.document_id
                WHERE dv.id=:id
            """), {"id": version_id}).fetchone()
        import os
        root = Path(os.environ.get("KNOWLEDGE_STORAGE_ROOT", "/data/knowledge"))
        file_path = root / str(version[2])
        run_ingest(int(version[1]), str(file_path), file_path.name, version[3], callback_url="")
        with engine.begin() as conn:
            conn.execute(text("UPDATE ingestion_job SET status='READY', lease_until=NULL WHERE id=:id"), {"id": job_id})
            conn.execute(text("UPDATE document_version SET status='READY' WHERE id=:id"), {"id": version_id})
    except Exception as error:
        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE ingestion_job
                SET status='PENDING', last_error=:error, lease_until=NULL, next_retry_at=now() + interval '30 seconds'
                WHERE id=:id
            """), {"id": job_id, "error": str(error)[:500]})
    return True


def loop() -> None:
    while True:
        try:
            if not claim_once():
                time.sleep(2)
        except Exception:
            time.sleep(2)


def start() -> None:
    threading.Thread(target=loop, name="ingest-jobs", daemon=True).start()
