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

## 故障排查

| 现象 | 排查 |
|------|------|
| 后端无法启动 | `make logs-backend` 查看数据库连接与迁移 |
| 前端 502 | 检查 backend healthcheck 是否通过 |
| 限流误触发 | 调整 `RATE_LIMIT_MAX_REQUESTS` / `RATE_LIMIT_WINDOW_SECONDS` |
