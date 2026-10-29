#!/usr/bin/env bash
# 开发模式启动后端
set -euo pipefail
cd "$(dirname "$0")"
exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 18000 --reload
