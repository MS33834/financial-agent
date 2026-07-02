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

升级前务必先备份数据库（见「备份」一节），并保留上一个镜像 tag 以便回滚。

## 回滚流程

升级后发现异常时，按以下步骤回滚：

```bash
# 1. 回退代码到上一个稳定版本
git checkout <previous-stable-tag>

# 2. 如有数据库迁移，先回滚迁移（确认 down 脚本安全后再执行）
cd backend && alembic downgrade -1

# 3. 重新构建并启动上一个版本镜像
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# 4. 验证服务健康
curl -fsS http://localhost:8000/health/ready
```

Kubernetes / Helm 部署回滚：

```bash
helm rollback financial-agent <REVISION_NUMBER>
kubectl rollout undo deployment/financial-agent-backend
```

注意：若新版本执行了不可逆的数据库迁移（如删列），回滚前需先从备份恢复数据库，再回滚应用版本。

## 备份

- PostgreSQL：定时 `pg_dump` 导出
- MinIO：`mc mirror` 同步 bucket
- 配置文件：`.env` 纳入密钥管理工具

PostgreSQL 定时备份示例（crontab，每天 02:00 执行，保留 14 天）：

```bash
0 2 * * * docker exec financial-agent-postgres pg_dump -U postgres dify | gzip > /backup/pg_$(date +\%F).sql.gz && find /backup -name "pg_*.sql.gz" -mtime +14 -delete
```

MinIO 异步同步示例：

```bash
mc alias set local http://localhost:9000 minioadmin minioadmin123
mc mirror --overwrite local/financial-agent backup/financial-agent
```

## HTTPS / TLS 配置

生产环境必须启用 HTTPS。两种常见方式：

1. **反向代理终止 TLS（推荐）**：在 Nginx / Ingress 层配置证书，后端仍走 HTTP。
   - Docker Compose：在 `frontend` 容器的 Nginx 中挂载证书并监听 443。
   - Kubernetes：通过 Ingress + cert-manager 自动签发 Let's Encrypt 证书（见 `values.yaml` 的 `ingress.tls`）。
2. **后端直挂证书**：Uvicorn 以 `--ssl-keyfile` / `--ssl-certfile` 启动，仅适用于无网关的小型部署。

证书过期前 30 天需续期；cert-manager 用户可配置 `cert-manager.io/cluster-issuer` 自动续期。

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

## 生产环境检查清单

正式上线前请逐项确认。任一项未满足都应视为不具备上线条件。

### 安全

- [ ] SECRET_KEY 已修改为 32+ 字符的随机值
- [ ] CORS_ORIGINS 已配置为具体前端域名（非通配符 `*`）
- [ ] HTTPS/TLS 已配置
- [ ] ABAC 权限策略已配置
- [ ] 审计日志已启用并持久化
- [ ] API Rate Limiting 已启用
- [ ] 镜像安全扫描已通过（Trivy 0 HIGH/CRITICAL）

### 数据与持久化

- [ ] 数据库已配置定期备份
- [ ] 数据卷已配置持久化

### 可观测性

- [ ] 日志收集已配置
- [ ] 监控告警已配置（Prometheus + Grafana）
- [ ] 健康检查端点已配置（`/health`、`/health/ready`）

### 资源与弹性

- [ ] 资源限制已配置（CPU/Memory limits）

### 快速自检命令

```bash
# 1. 验证生产配置校验通过（app_env=production 时后端会强校验 SECRET_KEY / CORS）
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend \
  python -c "from app.config import get_settings; s=get_settings(); print('env=',s.app_env,'cors=',s.cors_origins_list)"

# 2. 验证健康检查端点
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8000/health/ready

# 3. 验证指标端点可访问
curl -fsS http://localhost:8000/metrics | head

# 4. 镜像安全扫描
make scan-backend TRIVY_EXIT_CODE=1
```
