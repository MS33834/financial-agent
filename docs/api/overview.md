# API 概览

后端基于 FastAPI 实现，基础路径为 `/api/v1`。本地启动后可通过 http://localhost:8000/docs 查看交互式 Swagger 文档。

## 1. 认证方式

除登录接口外，大部分接口需要携带 JWT Token：

```http
Authorization: Bearer <access_token>
```

获取 Token：

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "change-me"}'
```

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer"
  }
}
```

## 2. 通用响应格式

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

- `code=0` 表示成功，非 0 表示业务错误
- HTTP 状态码遵循 REST 语义：200/201/204 成功，400 参数错误，401/403 权限错误，404 资源不存在，500 服务器错误

## 3. 核心端点

| 端点 | 方法 | 说明 | 主要角色 |
|------|------|------|----------|
| `/auth/login` | POST | 用户登录 | 任意 |
| `/auth/me` | GET | 获取当前用户信息 | 任意 |
| `/documents/upload` | POST | 上传 PDF/Excel 文件 | admin/finance_manager |
| `/documents` | GET | 文档列表 | 任意 |
| `/documents/{id}` | GET | 文档详情 | 任意 |
| `/queries/nl2sql` | POST | 自然语言查询 | 任意 |
| `/reports` | GET/POST | 报告列表/创建报告 | 查看/创建权限 |
| `/reports/{id}` | GET | 报告详情 | 任意 |
| `/reports/{id}/export` | POST | 导出 PDF/Excel | admin/finance_manager |
| `/approvals/{id}/action` | POST | 审批报告 | admin/finance_manager/auditor |
| `/audit/logs` | GET | 审计日志 | admin/auditor |
| `/dashboard/summary` | GET | 仪表盘汇总 | 任意 |
| `/health/ready` | GET | 就绪探针 | 任意 |

## 4. 错误处理

业务错误示例：

```json
{
  "code": 1001,
  "message": "报告不存在",
  "data": null
}
```

验证错误示例：

```json
{
  "detail": [
    {
      "loc": ["body", "title"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

## 5. 限流

生产环境默认启用限流（`RATE_LIMIT_ENABLED=true`），基于 Redis 实现。超限返回：

```json
{
  "code": 429,
  "message": "Rate limit exceeded"
}
```

## 6. Postman 集合

完整的请求示例见 [`financial-agent.postman_collection.json`](./financial-agent.postman_collection.json)，可导入 Postman 或 Bruno 直接调用。
