# 部署手册

## 环境要求

- Docker Engine ≥ 24.0
- Docker Compose ≥ 2.20
- 生产服务器 ≥ 4 核 / 16GB 内存 / 50GB SSD

## 快速生产部署

```bash
# 1. 复制并修改配置
cp .env.example .env
# 必改项：SECRET_KEY、CORS_ORIGINS、数据库密码

# 2. 生产模式启动
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 3. 查看服务状态
make status
```

## 关键配置说明

| 变量 | 说明 | 生产建议 |
|------|------|----------|
| `SECRET_KEY` | JWT/加密密钥 | ≥32 位随机字符串 |
| `CORS_ORIGINS` | 允许的前端域名 | 限制为实际域名，不要用 `*` |
| `RATE_LIMIT_ENABLED` | 请求限流开关 | 保持 `true` |
| `DATABASE_URL` | PostgreSQL 连接 | 使用独立数据库，避免复用 Dify |
| `APP_ENV` | 运行环境 | 生产设为 `production` |

## 升级流程

```bash
# 拉取最新代码
git pull origin main

# 重新构建并启动
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# 查看后端日志确认无异常
make logs-backend
```

## 备份

- PostgreSQL：定时 `pg_dump` 导出
- MinIO：`mc mirror` 同步 bucket
- 配置文件：`.env` 纳入密钥管理工具

## 健康检查端点

后端提供三个健康检查端点（挂载在 `/health` 路由下，实际访问路径取决于网关是否加了 `/api/v1` 前缀）：

| 端点 | 用途 | 返回 |
|------|------|------|
| `GET /health` | 服务是否可响应 | `BaseResponse`（`code=0, message=ok`） |
| `GET /health/live` | 存活探针（liveness） | `BaseResponse`（`code=0, message=alive`） |
| `GET /health/ready` | 就绪探针（readiness），检查 DB、Redis、MinIO | `HealthReadyResponse` |

`/health/ready` 的 JSON 格式示例：

```json
{
  "status": "ready",
  "dependencies": {
    "database": {"status": "up", "latency_ms": 2.15, "message": "connected"},
    "redis": {"status": "up", "latency_ms": 1.03, "message": "connected"},
    "minio": {"status": "up", "latency_ms": 5.21, "message": "connected"}
  }
}
```

任一依赖不可用时返回 HTTP 503，`status` 为 `not_ready`，并附带失败依赖的错误信息。建议在 Kubernetes 中这样配置探针：

```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 10
readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
```

## 优雅关闭行为

容器收到 `SIGTERM` 后：

1. Uvicorn 停止接受新的 TCP 连接；
2. 等待正在处理的请求完成，最长等待 `--timeout-graceful-shutdown 30` 秒；
3. 触发 FastAPI `lifespan` 的 shutdown 阶段，释放 SQLAlchemy 数据库连接池；
4. 进程退出。

Dockerfile 已配置 `--timeout-graceful-shutdown 30` 与 `--lifespan on`，`entrypoint.sh` 使用 `exec` 替换进程以确保信号直达 Uvicorn。若部署在 Kubernetes 中，建议设置 `terminationGracePeriodSeconds` 大于 30 秒（如 60 秒），并视情况添加 `preStop: sleep 10` 让 Service / Ingress 先将 Pod 从流量中摘除。

## 配置热加载

生产环境推荐通过管理接口进行受控的配置热加载，**不启用文件监听热重载**。

- 接口：`POST /api/v1/admin/reload-config`
- 权限：必须具备 `admin` 角色，且满足 ABAC 策略 `system_config:reload`。
- 行为：重新读取环境变量 / `.env` 文件，清空 `get_settings` 与 MinIO 客户端缓存；返回当前生效的非敏感配置快照。

限制：

- 数据库连接池、`celery_app` broker URL 等模块级全局对象在导入时初始化，热加载不会刷新它们；修改 `DATABASE_URL`、`REDIS_URL` 等基础连接配置后仍需重启 Pod。
- 仅适合在运行时调整限流阈值、日志级别、功能开关等业务层配置。

开发环境如需文件监听 reload，可在本地启动时附加 `uvicorn --reload`，生产镜像不启用该参数。

## 故障排查

| 现象 | 排查 |
|------|------|
| 后端无法启动 | `make logs-backend` 查看数据库连接与迁移 |
| 前端 502 | 检查 backend healthcheck 是否通过 |
| 限流误触发 | 调整 `RATE_LIMIT_MAX_REQUESTS` / `RATE_LIMIT_WINDOW_SECONDS` |
| Pod 被强制终止 | 检查 `terminationGracePeriodSeconds` 是否大于 Uvicorn graceful timeout |
