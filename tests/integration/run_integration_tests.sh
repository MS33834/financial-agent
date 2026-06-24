#!/usr/bin/env bash
# ==================================================================
# 本地 Docker 集成测试入口
# 启动 PostgreSQL/Redis/MinIO，运行后端集成测试，然后清理环境。
# 前置要求：
#   - Docker Engine >= 24.0
#   - Docker Compose >= 2.20
#   - 已在 backend/ 目录执行 `pip install -e ".[dev]"`
# 用法：
#   ./tests/integration/run_integration_tests.sh
# ==================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BACKEND_DIR="${PROJECT_ROOT}/backend"

COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.dependencies.yml"
COMPOSE_PROJECT="financial-agent-integration"

export APP_ENV="integration"
export DATABASE_URL="postgresql+psycopg://postgres:difyai123456@localhost:5432/financial_agent_test"
export REDIS_URL="redis://:difyai123456@localhost:6379/3"
export MINIO_ENDPOINT="localhost:9000"
export MINIO_ACCESS_KEY="minioadmin"
export MINIO_SECRET_KEY="minioadmin123"
export MINIO_BUCKET="financial-agent-test"
export MINIO_PUBLIC_URL="http://localhost:9000"
export RATE_LIMIT_ENABLED="false"
export CELERY_BROKER_URL="${REDIS_URL}"
export CELERY_RESULT_BACKEND="${REDIS_URL}"

cleanup() {
  echo "==> Cleaning up integration test services..."
  docker compose -f "${COMPOSE_FILE}" -p "${COMPOSE_PROJECT}" down -v || true
}

trap cleanup EXIT

echo "==> Starting integration test dependencies..."
docker compose -f "${COMPOSE_FILE}" -p "${COMPOSE_PROJECT}" up -d --wait

echo "==> Waiting for services to be healthy..."
# docker compose up --wait 依赖 healthcheck；额外兜底等待
for _ in {1..30}; do
  if docker compose -f "${COMPOSE_FILE}" -p "${COMPOSE_PROJECT}" ps | grep -q "unhealthy\|starting"; then
    sleep 2
  else
    break
  fi
done

echo "==> Running backend integration tests..."
cd "${BACKEND_DIR}"
python -m pytest ../tests/integration -v "$@"

echo "==> Integration tests finished successfully."
