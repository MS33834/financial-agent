# 集成测试指南

## 1. 概述

集成测试用于验证后端服务与真实中间件（PostgreSQL、Redis、MinIO）的交互。测试代码位于 [`tests/integration`](../../tests/integration) 目录，不依赖 SQLite 内存数据库，而是连接真实的 Docker 化服务。

## 2. 前置要求

- Docker Engine ≥ 24.0
- Docker Compose ≥ 2.20
- 后端 Python 依赖已安装：`cd backend && pip install -e ".[dev]"`

## 3. 一键运行

```bash
./tests/integration/run_integration_tests.sh
```

脚本会自动完成：

1. 启动 PostgreSQL、Redis、MinIO
2. 等待服务健康
3. 运行 `tests/integration` 下的测试
4. 停止并清理容器与数据卷

## 4. 手动运行

如果希望保持服务运行以便调试：

```bash
# 启动依赖
cd tests/integration
docker compose -f docker-compose.dependencies.yml up -d --wait

# 运行测试
cd ../../backend
APP_ENV=integration \
  DATABASE_URL=postgresql+psycopg://postgres:difyai123456@localhost:5432/financial_agent_test \
  REDIS_URL=redis://:difyai123456@localhost:6379/3 \
  MINIO_ENDPOINT=localhost:9000 \
  MINIO_ACCESS_KEY=minioadmin \
  MINIO_SECRET_KEY=minioadmin123 \
  MINIO_BUCKET=financial-agent-test \
  MINIO_PUBLIC_URL=http://localhost:9000 \
  RATE_LIMIT_ENABLED=false \
  python -m pytest ../tests/integration -v

# 清理
cd ../tests/integration
docker compose -f docker-compose.dependencies.yml down -v
```

## 5. 添加新的集成测试

在 `tests/integration/` 目录新建 `test_integration_*.py` 文件，使用环境变量中的真实服务地址即可。例如：

```python
def test_real_redis_connection() -> None:
    import redis
    from app.config import get_settings

    settings = get_settings()
    r = redis.from_url(settings.redis_url)
    r.set("test-key", "ok")
    assert r.get("test-key") == b"ok"
```

## 6. CI 中运行

在 GitHub Actions 中可添加如下步骤：

```yaml
- name: Start integration dependencies
  run: docker compose -f tests/integration/docker-compose.dependencies.yml up -d --wait

- name: Run integration tests
  working-directory: backend
  env:
    APP_ENV: integration
    DATABASE_URL: postgresql+psycopg://postgres:difyai123456@localhost:5432/financial_agent_test
    REDIS_URL: redis://:difyai123456@localhost:6379/3
    MINIO_ENDPOINT: localhost:9000
    MINIO_ACCESS_KEY: minioadmin
    MINIO_SECRET_KEY: minioadmin123
    MINIO_BUCKET: financial-agent-test
    MINIO_PUBLIC_URL: http://localhost:9000
    RATE_LIMIT_ENABLED: "false"
  run: python -m pytest ../tests/integration -v

- name: Stop integration dependencies
  if: always()
  run: docker compose -f tests/integration/docker-compose.dependencies.yml down -v
```
