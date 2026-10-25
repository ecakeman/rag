"""M1W2-2 验收:/health、/ingest 鉴权与 202、状态与删除路由。"""
from fastapi.testclient import TestClient

from app.config import settings
from app.ingestion import pipeline
from app.main import app

client = TestClient(app)
TOKEN = {"X-Internal-Token": settings.internal_token}


def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_ingest_without_token_401():
    r = client.post("/ingest", json={"docId": 1, "filePath": "p", "fileName": "f",
                                     "title": "t", "callbackUrl": "http://c"})
    assert r.status_code == 401


def test_ingest_accepted_and_dispatches_background(monkeypatch):
    dispatched = []
    monkeypatch.setattr(pipeline, "run_ingest",
                        lambda *a, **k: dispatched.append(a))
    r = client.post("/ingest", headers=TOKEN,
                    json={"docId": 5, "filePath": "data/files/5.pdf", "fileName": "5.pdf",
                          "title": "手册", "callbackUrl": "http://cb"})
    assert r.status_code == 202
    assert r.json() == {"status": "QUEUED"}
    assert dispatched and dispatched[0][0] == 5


def test_status_route(monkeypatch):
    monkeypatch.setattr(pipeline, "ingest_status",
                        lambda d: {"docId": d, "status": "READY", "chunkCount": 4})
    r = client.get("/ingest/5/status", headers=TOKEN)
    assert r.status_code == 200
    assert r.json()["status"] == "READY"


def test_delete_route(monkeypatch):
    deleted = []
    monkeypatch.setattr(pipeline, "delete_doc_chunks", lambda d: deleted.append(d))
    r = client.delete("/ingest/5", headers=TOKEN)
    assert r.status_code == 204
    assert deleted == [5]
