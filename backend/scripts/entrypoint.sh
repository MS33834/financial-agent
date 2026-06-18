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
  alembic upgrade head
fi

# 初始化默认租户和管理员
python scripts/bootstrap.py

# 执行主命令（exec 替换进程，保证信号正确传递）
exec "$@"
