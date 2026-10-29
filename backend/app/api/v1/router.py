"""v1 路由汇总。"""
from fastapi import APIRouter

from app.api.v1 import (
    alert_events,
    alerts,
    audit,
    auth,
    channels,
    findings,
    inspections,
    metrics,
    operations,
    rules,
    system,
    targets,
    users,
)

api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(targets.router)
api_router.include_router(inspections.router)
api_router.include_router(findings.router)
api_router.include_router(rules.router)
api_router.include_router(alerts.router)
api_router.include_router(channels.router)
api_router.include_router(alert_events.router)
api_router.include_router(metrics.router)
api_router.include_router(operations.router)
api_router.include_router(audit.router)
