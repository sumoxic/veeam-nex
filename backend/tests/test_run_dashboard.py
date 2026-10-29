"""按巡检轮次的仪表盘：任务/存储库/还原点/发现项聚合。"""
from app.models.finding import Finding
from app.models.inspection import ClockSource, InspectionRun, RunStatus, RunTrigger
from app.models.target import Target
from app.services.metrics_service import recent_runs, run_dashboard
from app.utils.fingerprint import build_fingerprint
from app.utils.timeutil import utcnow


def _run_with_inventory(db):
    now = utcnow().replace(tzinfo=None)
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

    run = InspectionRun(
        target_id=target.id,
        trigger_type=RunTrigger.MANUAL,
        status=RunStatus.SUCCESS,
        started_at=now,
        finished_at=now,
        clock_source=ClockSource.VBR,
        vbr_server_time=now,
        vbr_build="13.1.0.411",
        findings_total=3,
        findings_critical=1,
        findings_warn=1,
        findings_info=1,
        created_at=now,
        inventory_json={
            "server": {"name": "vbr01", "buildVersion": "13.1.0.411"},
            "license": {
                "edition": "EnterprisePlus",
                "status": "Valid",
                "instanceLicenseSummary": {
                    "usedInstancesNumber": 2,
                    "licensedInstancesNumber": 10,
                },
            },
            "jobs": [
                {"id": "j1", "name": "Job 1", "lastResult": "Success", "status": "Stopped"},
                {"id": "j2", "name": "Job 2", "lastResult": "Failed", "status": "Stopped"},
            ],
            "jobConfigs": [{"id": "j2", "isDisabled": True}],
            "repositories": [
                {
                    "id": "r1",
                    "name": "Repo 1",
                    "capacityGB": 200,
                    "freeGB": 50,
                    "isOnline": True,
                }
            ],
            "restorePoints": [
                {"id": "rp1", "name": "vm1", "malwareStatus": "Clean"}
            ],
            "backupObjects": [
                {"id": "o1", "name": "vm1", "size": 1024, "lastRunFailed": False}
            ],
            "proxies": [{"id": "p1", "name": "Proxy", "isOnline": True}],
            "managedServers": [{"id": "s1", "name": "esxi", "status": "Available"}],
            "sessions": [
                {
                    "id": "ss1",
                    "name": "Backup Job",
                    "creationTime": "2026-10-29T10:00:00+08:00",
                    "result": {"result": "Success"},
                }
            ],
        },
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    for level in ("critical", "warn", "info"):
        db.add(
            Finding(
                target_id=target.id,
                fingerprint=build_fingerprint(target.id, f"rule.{level}", level),
                rule_key=f"rule.{level}",
                category="job",
                level=level,
                subject=f"subject-{level}",
                subject_key=level,
                message=f"message-{level}",
                occurrences=1,
                first_seen_at=now,
                last_seen_at=now,
                last_run_id=run.id,
            )
        )
    db.commit()
    return target, run


def test_run_dashboard_aggregates_inventory(db):
    _, run = _run_with_inventory(db)
    data = run_dashboard(db, run.id)

    assert data["run"]["id"] == run.id
    assert data["target"]["name"] == "t1"
    assert data["license"]["used_percent"] == 20

    assert data["job_stats"] == {
        "total": 2,
        "success": 1,
        "warning": 0,
        "failed": 1,
        "running": 0,
        "disabled": 1,
        "unknown": 0,
    }
    assert data["repo_stats"]["free_percent"] == 25
    assert data["repo_stats"]["used_gb"] == 150

    assert data["restore_points"]["total"] == 1
    assert data["restore_points"]["clean"] == 1
    assert data["backup_objects"]["total_size"] == 1024

    assert data["findings_by_level"] == {"critical": 1, "warn": 1, "info": 1}
    # 严重项排在最前
    assert data["findings"][0]["level"] == "critical"

    assert data["proxies"][0]["name"] == "Proxy"
    assert data["managed_servers"][0]["status"] == "Available"
    assert data["sessions"][0]["result"] == "Success"


def test_recent_runs_includes_target_name(db):
    _, run = _run_with_inventory(db)
    items = recent_runs(db)
    assert items[0]["id"] == run.id
    assert items[0]["target_name"] == "t1"
    assert items[0]["status"] == "success"
