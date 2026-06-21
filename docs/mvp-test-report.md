# MVP 测试报告

## 测试范围

本次测试覆盖后端 API、核心业务流程、安全场景与性能基线。

## 测试环境

- Python 3.14
- SQLite（测试）/ PostgreSQL 15（生产）
- FastAPI + Celery + Redis
- 测试日期：2026-06-21

## 单元与集成测试

```bash
cd backend
APP_ENV=testing DATABASE_URL="sqlite:///./test.db" RATE_LIMIT_ENABLED=false python -m pytest
```

结果：143 passed, 0 failed

## 测试覆盖率

```
pytest --cov=app --cov-report=term
```

结果：84%（目标 ≥60%）

## 性能基线

```bash
python scripts/run_benchmark_with_server.py
```

| 端点 | P95 响应时间 | 状态 |
|------|-------------|------|
| GET /health | 0.004s | ✅ |
| GET /health/ready | 0.002s | ✅ |
| GET /metrics | 0.042s | ✅ |
| GET /api/v1/auth/me | 0.005s | ✅ |
| POST /api/v1/queries/nl2sql | 0.012s | ✅ |
| GET /api/v1/reports | 0.015s | ✅ |
| GET /api/v1/documents | 0.008s | ✅ |
| GET /api/v1/approvals | 0.005s | ✅ |
| GET /api/v1/audit/logs | 0.007s | ✅ |

基线要求：P95 < 3s。所有接口均达标。

## 功能验收

| 功能 | 状态 |
|------|------|
| 用户登录与 JWT 鉴权 | ✅ |
| 基于角色的权限控制 | ✅ |
| 财务报告生成与导出 | ✅ |
| 文档上传与解析 | ✅ |
| 自然语言查询（Text2SQL） | ✅ |
| SQL 沙箱安全防护 | ✅ |
| 人工审批流程 | ✅ |
| 审计日志记录 | ✅ |
| IM 机器人审批通知 | ✅ |

## 安全验收

| 项目 | 状态 |
|------|------|
| SQL 注入参数绑定 | ✅ |
| 登录输入长度校验 | ✅ |
| 安全响应头 | ✅ |
| 速率限制 | ✅ |
| SQL 沙箱禁止危险操作 | ✅ |

## 结论

MVP 全部功能与非功能验收项均已通过，满足上线演示条件。
