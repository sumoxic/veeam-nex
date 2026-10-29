"""远程操作两步确认：令牌校验、过期、执行与返回值。"""
from datetime import timedelta

import pytest

from app.models.target import OperationStatus, Target
from app.services import operation_service, target_service
from app.services.operation_service import (
    confirm_operation,
    create_operation,
    reject_operation,
)
from app.utils.errors import ConflictError, ForbiddenError
from app.utils.timeutil import utcnow


class FakeClient:
    def __init__(self, response=None, error=None, api_version="1.3-rev2"):
        self.response = response
        self.error = error
        self.api_version = api_version
        self.calls = []

    def ensure_version(self):
        return self.api_version

    def post(self, path, body=None):
        self.calls.append((path, body))
        if self.error:
            raise self.error
        return self.response


def _target(db):
    target = Target(
        name="t1",
        host="10.0.0.1",
        port=9419,
        username="Administrator",
        password_enc="fernet:placeholder",
    )
    db.add(target)
    db.commit()
    db.refresh(target)
    return target


def _patch_client(monkeypatch, target, client):
    monkeypatch.setattr(target_service, "get_target", lambda db, tid: target)
    monkeypatch.setattr(target_service, "build_client", lambda t: client)


def test_create_only_returns_token_and_does_not_execute(db, monkeypatch):
    target = _target(db)
    client = FakeClient()
    _patch_client(monkeypatch, target, client)

    row = create_operation(db, target.id, "proxy.disable", {"proxy_id": "p1"})
    assert row.status == OperationStatus.PENDING
    assert len(row.confirmation_token) == 64
    assert client.calls == []


def test_wrong_token_is_rejected_without_executing(db, monkeypatch):
    target = _target(db)
    client = FakeClient()
    _patch_client(monkeypatch, target, client)
    row = create_operation(db, target.id, "proxy.disable", {"proxy_id": "p1"})

    with pytest.raises(ForbiddenError):
        confirm_operation(db, row, "deadbeef")

    assert row.status == OperationStatus.PENDING
    assert client.calls == []


def test_expired_token_marks_operation_expired(db, monkeypatch):
    target = _target(db)
    client = FakeClient()
    _patch_client(monkeypatch, target, client)
    row = create_operation(db, target.id, "proxy.disable", {"proxy_id": "p1"})
    row.token_expires_at = utcnow().replace(tzinfo=None) - timedelta(minutes=1)
    db.commit()

    with pytest.raises(ForbiddenError):
        confirm_operation(db, row, row.confirmation_token)

    assert row.status == OperationStatus.EXPIRED
    assert client.calls == []


def test_correct_token_executes_proxy_operation(db, monkeypatch):
    target = _target(db)
    client = FakeClient(response={"response": None})
    _patch_client(monkeypatch, target, client)
    row = create_operation(db, target.id, "proxy.disable", {"proxy_id": "p1"})

    updated = confirm_operation(db, row, row.confirmation_token)

    assert updated.status == OperationStatus.SUCCEEDED
    assert client.calls == [("/api/v1/backupInfrastructure/proxies/p1/disable", None)]


def test_job_start_builds_body_and_records_task_id(db, monkeypatch):
    target = _target(db)
    client = FakeClient(response={"taskId": "task-9"})
    _patch_client(monkeypatch, target, client)
    row = create_operation(
        db,
        target.id,
        "job.start",
        {"job_id": "job-1", "perform_active_full": True},
    )

    updated = confirm_operation(db, row, row.confirmation_token)

    assert updated.status == OperationStatus.SUCCEEDED
    assert updated.vbr_task_id == "task-9"
    assert client.calls == [
        ("/api/v1/jobs/job-1/start", {"performActiveFull": True})
    ]


def test_vbr_failure_marks_operation_failed(db, monkeypatch):
    from app.vbr.exceptions import VbrError

    target = _target(db)
    client = FakeClient(error=VbrError("boom"))
    _patch_client(monkeypatch, target, client)
    row = create_operation(db, target.id, "proxy.disable", {"proxy_id": "p1"})

    with pytest.raises(ConflictError):
        confirm_operation(db, row, row.confirmation_token)

    assert row.status == OperationStatus.FAILED
    assert "boom" in (row.error_message or "")


def test_reject_only_pending(db, monkeypatch):
    target = _target(db)
    client = FakeClient()
    _patch_client(monkeypatch, target, client)
    row = create_operation(db, target.id, "proxy.disable", {"proxy_id": "p1"})

    updated = reject_operation(db, row)
    assert updated.status == OperationStatus.REJECTED
    with pytest.raises(ConflictError):
        reject_operation(db, row)


def test_token_depends_on_params(db, monkeypatch):
    target = _target(db)
    client = FakeClient()
    _patch_client(monkeypatch, target, client)
    a = create_operation(db, target.id, "proxy.disable", {"proxy_id": "p1"})
    b = create_operation(db, target.id, "proxy.disable", {"proxy_id": "p2"})
    assert a.confirmation_token != b.confirmation_token


def test_vbr12_rejects_unsupported_operation(db, monkeypatch):
    target = _target(db)
    client = FakeClient(api_version="1.2-rev1")
    _patch_client(monkeypatch, target, client)
    row = create_operation(db, target.id, "proxy.disable", {"proxy_id": "p1"})

    with pytest.raises(ConflictError):
        confirm_operation(db, row, row.confirmation_token)

    assert client.calls == []
    assert row.status == OperationStatus.FAILED
