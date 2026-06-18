# 企业级财务智能体 - 后端服务

## 本地开发

### 1. 安装依赖

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. 配置环境变量

```bash
cp ../.env.example .env
# 修改 DATABASE_URL、REDIS_URL、SECRET_KEY 等
```

### 3. 运行数据库迁移

```bash
alembic upgrade head
```

### 4. 启动服务

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. 运行测试

```bash
pytest
```

## 主要模块

| 模块 | 职责 |
|------|------|
| `app/config.py` | Pydantic Settings 配置管理 |
| `app/database.py` | SQLAlchemy 引擎、会话、基类 |
| `app/models/` | 数据库 ORM 模型 |
| `app/schemas/` | Pydantic 请求/响应模型 |
| `app/routers/` | FastAPI 路由 |
| `app/services/` | 业务服务层 |
| `app/security.py` | JWT、密码哈希、认证依赖 |
| `app/logger.py` | 结构化日志 |
| `alembic/` | 数据库迁移 |
| `tests/` | 测试用例 |

## API 列表

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/api/v1/auth/login` | 登录 |
| GET | `/api/v1/auth/me` | 当前用户 |
| POST | `/api/v1/documents` | 创建文档解析任务 |
| GET | `/api/v1/documents` | 文档列表 |
| GET | `/api/v1/documents/{id}` | 文档详情 |
| POST | `/api/v1/queries/nl2sql` | 自然语言查数 |
| POST | `/api/v1/reports` | 创建报告 |
| GET | `/api/v1/reports` | 报告列表 |
| GET | `/api/v1/reports/{id}` | 报告详情 |
| POST | `/api/v1/approvals/{id}/action` | 审核操作 |
| GET | `/api/v1/audit/logs` | 审计日志 |
