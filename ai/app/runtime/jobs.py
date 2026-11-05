"""摄取任务租约。执行中续租，旧 fencing token 不能回写结果。"""
from __future__ import annotations

import os
import threading
import time
import uuid
from pathlib import Path

from sqlalchemy import text

from app.db import engine
from app.ingestion.pipeline import LostLease, run_knowledge_ingest


def _renew(job_id: int, owner: str, token: int, stop: threading.Event) -> None:
    while not stop.wait(30):
        with engine.begin() as conn:
            row = conn.execute(text("""
                UPDATE ingestion_job
                SET lease_until = now() + interval '2 minutes'
                WHERE id=:id AND lease_owner=:owner AND fencing_token=:token
                  AND status='PROCESSING' AND lease_until > now()
                RETURNING id
            """), {"id": job_id, "owner": owner, "token": token}).fetchone()
        if row is None:
            stop.set()
            return


def claim_once() -> bool:
    owner = str(uuid.uuid4())
    with engine.begin() as conn:
        row = conn.execute(text("""
            UPDATE ingestion_job
            SET status='PROCESSING', attempts=attempts+1, lease_owner=:owner,
                fencing_token=fencing_token+1, lease_until=now() + interval '2 minutes'
            WHERE id = (
                SELECT id FROM ingestion_job
                WHERE (
                    status = 'PENDING'
                    OR (status = 'PROCESSING' AND (lease_until IS NULL OR lease_until < now()))
                )
                  AND (next_retry_at IS NULL OR next_retry_at <= now())
                ORDER BY id
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING id, document_version_id, fencing_token
        """), {"owner": owner}).fetchone()
    if row is None:
        return False
    job_id, version_id, token = int(row[0]), int(row[1]), int(row[2])
    stop = threading.Event()
    threading.Thread(target=_renew, args=(job_id, owner, token, stop), daemon=True).start()
    try:
        with engine.connect() as conn:
            version = conn.execute(text("""
                SELECT dv.id, dv.document_id, dv.storage_path, d.title
                FROM document_version dv JOIN document d ON d.id=dv.document_id
                WHERE dv.id=:id
            """), {"id": version_id}).fetchone()
        root = Path(os.environ.get("KNOWLEDGE_STORAGE_ROOT", "/data/knowledge"))
        file_path = root / str(version[2])
        if stop.is_set():
            return True
        run_knowledge_ingest(
            int(version[1]), str(file_path), file_path.name, version[3],
            document_version_id=int(version[0]), job_id=job_id,
            lease_owner=owner, fencing_token=token,
        )
        if stop.is_set():
            return True
        with engine.begin() as conn:
            updated = conn.execute(text("""
                UPDATE ingestion_job
                SET status='READY', lease_until=NULL
                WHERE id=:id AND lease_owner=:owner AND fencing_token=:token
                  AND status='PROCESSING' AND lease_until > now()
                RETURNING id
            """), {"id": job_id, "owner": owner, "token": token}).fetchone()
            if updated is None:
                return True
            conn.execute(text("UPDATE document_version SET status='READY' WHERE id=:id"), {"id": version_id})
            conn.execute(text("UPDATE document SET current_version_id=:version WHERE id=:doc"),
                         {"version": version_id, "doc": int(version[1])})
        from app.retrieval import bm25
        bm25.rebuild()
    except LostLease:
        return True
    except Exception as error:
        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE ingestion_job
                SET status='PENDING', last_error=:error, lease_until=NULL,
                    next_retry_at=now() + interval '30 seconds'
                WHERE id=:id AND lease_owner=:owner AND fencing_token=:token
            """), {"id": job_id, "owner": owner, "token": token, "error": str(error)[:500]})
    finally:
        stop.set()
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
