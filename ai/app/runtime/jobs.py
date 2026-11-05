"""摄取任务租约。执行中续租，旧 fencing token 不能回写结果。"""
from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from pathlib import Path

from sqlalchemy import text

from app.config import settings
from app.db import engine
from app.ingestion.pipeline import LostLease, run_knowledge_ingest

log = logging.getLogger(__name__)
_GRACE_SECONDS = 24 * 60 * 60
_index_dirty = False
_index_retry_at = 0.0


def mark_index_dirty() -> None:
    global _index_dirty, _index_retry_at
    _index_dirty = True
    _index_retry_at = time.monotonic()


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


def _refresh_index() -> None:
    """索引刷新失败只留下重试标记，不改已经提交的摄取结果。"""
    global _index_dirty, _index_retry_at
    try:
        from app.retrieval import bm25
        bm25.rebuild()
        _index_dirty = False
    except Exception:
        _index_dirty = True
        _index_retry_at = time.monotonic()
        log.error("BM25 刷新失败，摄取结果保持不变", exc_info=True)


def _fail_versions(conn, version_ids: list[int]) -> None:
    for version_id in version_ids:
        conn.execute(text("""
            UPDATE document_version SET status='FAILED'
            WHERE id=:id AND status <> 'READY'
        """), {"id": version_id})


def _fail_expired() -> None:
    """达到尝试上限且没有有效租约的任务改为 FAILED。"""
    with engine.begin() as conn:
        rows = conn.execute(text("""
            UPDATE ingestion_job
            SET status='FAILED', lease_until=NULL,
                last_error=COALESCE(last_error, 'attempt limit reached')
            WHERE attempts >= :max
              AND (
                    status = 'PENDING'
                    OR (status = 'PROCESSING' AND (lease_until IS NULL OR lease_until < now()))
                  )
            RETURNING document_version_id
        """), {"max": settings.knowledge_ingest_max_attempts}).fetchall()
        _fail_versions(conn, [int(row[0]) for row in rows])


def _requeue(job_id: int, owner: str, token: int, message: str) -> None:
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE ingestion_job
            SET status='PENDING', last_error=:error, lease_until=NULL,
                next_retry_at=now() + interval '30 seconds'
            WHERE id=:id AND lease_owner=:owner AND fencing_token=:token
              AND status='PROCESSING' AND lease_until > now()
        """), {"id": job_id, "owner": owner, "token": token, "error": message})


def _mark_failed(job_id: int, owner: str, token: int, version_id: int, message: str) -> None:
    with engine.begin() as conn:
        updated = conn.execute(text("""
            UPDATE ingestion_job
            SET status='FAILED', last_error=:error, lease_until=NULL
            WHERE id=:id AND lease_owner=:owner AND fencing_token=:token
              AND status='PROCESSING' AND lease_until > now()
            RETURNING id
        """), {"id": job_id, "owner": owner, "token": token, "error": message}).fetchone()
        if updated is not None:
            _fail_versions(conn, [version_id])


def claim_once() -> bool:
    _fail_expired()
    owner = str(uuid.uuid4())
    with engine.begin() as conn:
        row = conn.execute(text("""
            UPDATE ingestion_job
            SET status='PROCESSING', attempts=attempts+1, lease_owner=:owner,
                fencing_token=fencing_token+1, lease_until=now() + interval '2 minutes'
            WHERE id = (
                SELECT id FROM ingestion_job
                WHERE attempts < :max
                  AND (
                    status = 'PENDING'
                    OR (status = 'PROCESSING' AND (lease_until IS NULL OR lease_until < now()))
                  )
                  AND (next_retry_at IS NULL OR next_retry_at <= now())
                ORDER BY id
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING id, document_version_id, fencing_token, attempts
        """), {"owner": owner, "max": settings.knowledge_ingest_max_attempts}).fetchone()
    if row is None:
        return False
    job_id, version_id, token, attempts = int(row[0]), int(row[1]), int(row[2]), int(row[3])
    stop = threading.Event()
    threading.Thread(target=_renew, args=(job_id, owner, token, stop), daemon=True).start()
    committed = False
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
        committed = True
    except LostLease:
        return True
    except Exception as error:
        message = str(error)[:500]
        if attempts >= settings.knowledge_ingest_max_attempts:
            _mark_failed(job_id, owner, token, version_id, message)
        else:
            _requeue(job_id, owner, token, message)
    finally:
        stop.set()
    if committed:
        _refresh_index()
    return True


def sweep_orphans() -> None:
    """删除超过 24 小时、且数据库没有引用的上传文件。"""
    root = Path(os.environ.get("KNOWLEDGE_STORAGE_ROOT", "/data/knowledge")).resolve()
    if not root.is_dir():
        return
    cutoff = time.time() - _GRACE_SECONDS
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT storage_path FROM document_version")).fetchall()
    referenced = {str(row[0]) for row in rows}
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            path.resolve().relative_to(root)
            relative = path.relative_to(root).as_posix()
            if path.stat().st_mtime >= cutoff:
                continue
        except (OSError, ValueError):
            continue
        if relative in referenced:
            continue
        path.unlink(missing_ok=True)


def loop() -> None:
    last_sweep = time.monotonic() - 3600
    while True:
        try:
            now = time.monotonic()
            if _index_dirty and now - _index_retry_at >= 30:
                _refresh_index()
            if now - last_sweep >= 3600:
                last_sweep = now
                sweep_orphans()
            if not claim_once():
                time.sleep(2)
        except Exception:
            log.warning("摄取循环本轮失败", exc_info=True)
            time.sleep(2)


def start() -> None:
    threading.Thread(target=loop, name="ingest-jobs", daemon=True).start()
