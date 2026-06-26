#!/bin/sh
set -e

# 等待数据库就绪（开发/测试环境轻量等待，生产环境建议使用更健壮的 wait-for-it）
if [ -n "$DATABASE_URL" ]; then
  echo "Waiting for database..."
  for i in $(seq 1 30); do
    if python -c "import sqlalchemy; sqlalchemy.create_engine('$DATABASE_URL').connect().close()" 2>/dev/null; then
      echo "Database is ready."
      break
    fi
    echo "Database not ready, retrying in 2s..."
    sleep 2
  done
fi

# 生产环境应使用 Alembic 迁移；开发环境由 FastAPI lifespan 自动建表
if [ "$APP_ENV" = "production" ]; then
  echo "Running database migrations..."
  # 迁移失败兜底：重试 3 次，间隔递增，避免数据库主从切换瞬间导致迁移失败
  MIGRATION_MAX_RETRIES=3
  for attempt in $(seq 1 $MIGRATION_MAX_RETRIES); do
    if alembic upgrade head; then
      echo "Migrations applied successfully."
      break
    fi
    if [ "$attempt" -eq "$MIGRATION_MAX_RETRIES" ]; then
      echo "ERROR: Alembic migration failed after $MIGRATION_MAX_RETRIES attempts, aborting." >&2
      exit 1
    fi
    echo "Migration attempt $attempt failed, retrying in $((attempt * 5))s..." >&2
    sleep $((attempt * 5))
  done
fi

# 初始化默认租户和管理员
python scripts/bootstrap.py

# 执行主命令（exec 替换进程，保证信号正确传递）。
# Uvicorn 接收到 SIGTERM 后会停止接收新连接，等待在途请求完成（最多 30s），
# 并触发 lifespan shutdown 钩子释放数据库连接池。
exec "$@"
