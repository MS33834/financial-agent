# API 概览

后端基于 FastAPI 实现，所有业务接口统一前缀 `/api/v1`（健康检查除外）。本地启动后可通过 http://localhost:8000/docs 查看交互式 Swagger 文档，http://localhost:8000/redoc 查看 ReDoc 文档。

## 1. 认证方式

系统支持两种认证方式。除登录、健康检查、IM Webhook 回调、Dify 工具调用等公开接口外，其余接口均需携带凭证。

### 1.1 JWT Bearer Token（用户交互）

用户登录后使用 JWT 访问令牌：

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
  "message": "ok",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer"
  }
}
```

### 1.2 API Key（系统集成 / 自动化）

管理员/审计员可在「API Key 管理」页面创建 API Key，用于第三方系统对接或定时任务，避免长期持有用户 JWT：

```http
X-API-Key: <your_api_key>
```

API Key 具备：

- **Scope 授权**：如 `documents:read`、`documents:write` 等，按需授予最小权限。
- **生命周期管理**：支持启用、吊销（revoke）、删除（delete）、轮换（rotate，旧 Key 自动失效，明文仅返回一次）。
- **使用统计**：记录最近调用次数与时间，便于审计。

JWT 与 API Key 可在多数业务接口（文档、查询等）中互换使用；用户管理、配置重载等管理类接口仅接受 JWT。

## 2. 统一响应格式

所有业务接口返回统一的 `BaseResponse` 结构，`code=0` 表示成功。

### 2.1 DataResponse（单对象响应）

```json
{
  "code": 0,
  "message": "ok",
  "request_id": "uuid",
  "data": {}
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | int | 业务状态码，`0` 成功，非 `0` 失败 |
| `message` | string | 提示信息 |
| `request_id` | string\|null | 请求追踪 ID（来自 `X-Request-ID` 请求头，便于链路追踪） |
| `data` | object | 业务数据 |

### 2.2 PaginatedResponse（分页响应）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "total": 100,
    "page": 1,
    "page_size": 20,
    "items": []
  }
}
```

分页参数通过 query string 传递：`?page=1&page_size=20`（`page` 最小 1，`page_size` 取值 1–100，默认 20）。

### 2.3 HTTP 状态码语义

| HTTP 状态码 | 含义 |
|-------------|------|
| 200 / 201 / 204 | 成功（查询 / 创建 / 删除） |
| 400 | 参数错误 / 业务校验失败 |
| 401 | 未认证（缺少或无效凭证） |
| 403 | 无权限（RBAC / ABAC 拒绝） |
| 404 | 资源不存在 |
| 409 | 资源冲突（如用户名已存在） |
| 413 | 上传文件过大 |
| 422 | 请求体校验失败 |
| 429 | 限流 |
| 500 | 服务器内部错误 |

## 3. 完整端点列表

下表按模块分组列出全部端点（路径均省略公共前缀 `/api/v1`，健康检查除外）。鉴权列标注主要角色或方式：JWT 表示需登录用户，API Key 表示可用 API Key，公开表示无需凭证。

### 3.1 Auth 认证

| 端点 | 方法 | 说明 | 鉴权 |
|------|------|------|------|
| `/auth/login` | POST | 用户登录，返回 JWT | 公开 |
| `/auth/me` | GET | 获取当前用户信息 | JWT |

### 3.2 Users 用户管理

| 端点 | 方法 | 说明 | 鉴权 |
|------|------|------|------|
| `/users` | GET | 用户列表（分页） | JWT（admin） |
| `/users` | POST | 创建用户 | JWT（admin） |
| `/users/{user_id}` | PUT | 更新用户（邮箱/角色/启用/密码） | JWT（admin） |
| `/users/{user_id}` | DELETE | 删除用户 | JWT（admin） |
| `/users/{user_id}/reset-password` | POST | 重置指定用户密码 | JWT（admin） |

### 3.3 Documents 文档解析

| 端点 | 方法 | 说明 | 鉴权 |
|------|------|------|------|
| `/documents` | POST | 创建文档解析任务 | JWT/API Key（admin/finance_manager，`documents:write`） |
| `/documents/upload` | POST | 上传文件并创建解析任务（multipart） | JWT/API Key（admin/finance_manager，`documents:write`） |
| `/documents` | GET | 文档列表（分页，支持按状态筛选） | JWT/API Key（`documents:read`） |
| `/documents/{document_id}` | GET | 文档详情 | JWT/API Key（`documents:read`） |

### 3.4 Reports 财务报告

| 端点 | 方法 | 说明 | 鉴权 |
|------|------|------|------|
| `/reports` | POST | 创建报告 | JWT |
| `/reports` | GET | 报告列表（分页） | JWT |
| `/reports/{report_id}` | GET | 报告详情 | JWT |
| `/reports/{report_id}/export` | POST | 导出 PDF/Excel | JWT |

### 3.5 Queries 自然语言查询

| 端点 | 方法 | 说明 | 鉴权 |
|------|------|------|------|
| `/queries/nl2sql` | POST | 自然语言转 SQL 查询 | JWT |

### 3.6 Agent 智能问答

| 端点 | 方法 | 说明 | 鉴权 |
|------|------|------|------|
| `/agent/chat` | POST | Agent 多轮对话 | JWT |

### 3.7 Approvals 审批

| 端点 | 方法 | 说明 | 鉴权 |
|------|------|------|------|
| `/approvals` | GET | 待审批列表 | JWT（admin/auditor） |
| `/approvals/{report_id}/action` | POST | 审批报告（approve/reject） | JWT（admin/auditor） |

### 3.8 Audit 审计日志

| 端点 | 方法 | 说明 | 鉴权 |
|------|------|------|------|
| `/audit/logs` | GET | 审计日志列表（分页） | JWT（admin/auditor） |

### 3.9 API Keys 密钥管理

| 端点 | 方法 | 说明 | 鉴权 |
|------|------|------|------|
| `/api-keys` | POST | 创建 API Key（明文仅返回一次） | JWT（admin/auditor） |
| `/api-keys` | GET | API Key 列表 | JWT（admin/auditor） |
| `/api-keys/{key_id}/revoke` | POST | 吊销 API Key | JWT（admin/auditor） |
| `/api-keys/{key_id}` | DELETE | 删除 API Key | JWT（admin/auditor） |
| `/api-keys/{key_id}/rotate` | POST | 轮换 API Key | JWT（admin/auditor） |
| `/api-keys/me` | GET | 当前请求使用的 API Key 信息 | JWT/API Key |

### 3.10 IM 即时通讯

| 端点 | 方法 | 说明 | 鉴权 |
|------|------|------|------|
| `/im/dingtalk` | POST | 钉钉机器人回调 | 公开（签名校验） |
| `/im/feishu` | POST | 飞书机器人回调 | 公开（签名校验） |

### 3.11 IM User Mappings 用户映射

| 端点 | 方法 | 说明 | 鉴权 |
|------|------|------|------|
| `/im-user-mappings` | GET | 映射列表（分页） | JWT |
| `/im-user-mappings` | POST | 创建映射 | JWT |
| `/im-user-mappings/{mapping_id}` | DELETE | 删除映射 | JWT |

### 3.12 Notifications 通知

| 端点 | 方法 | 说明 | 鉴权 |
|------|------|------|------|
| `/notifications` | GET | 当前用户通知列表 | JWT |
| `/notifications/{notification_id}/read` | POST | 标记通知为已读 | JWT |

### 3.13 Access Policies 访问策略（ABAC）

| 端点 | 方法 | 说明 | 鉴权 |
|------|------|------|------|
| `/access-policies` | GET | 策略列表（分页） | JWT |
| `/access-policies` | POST | 创建策略 | JWT |
| `/access-policies/{policy_id}` | PUT | 更新策略 | JWT |
| `/access-policies/{policy_id}` | DELETE | 删除策略 | JWT |

### 3.14 Admin 系统管理

| 端点 | 方法 | 说明 | 鉴权 |
|------|------|------|------|
| `/admin/reload-config` | POST | 运行时重载配置 | JWT（admin，`system_config:reload`） |
| `/admin/config` | GET | 只读查看非敏感系统配置 | JWT（admin） |

### 3.15 Reflections 错误自省

| 端点 | 方法 | 说明 | 鉴权 |
|------|------|------|------|
| `/reflections` | GET | 自省日志列表（分页） | JWT |
| `/reflections/{reflection_id}` | GET | 自省详情 | JWT |
| `/reflections/{reflection_id}/resolve` | POST | 标记自省已处理 | JWT |

### 3.16 Dashboard 仪表盘 / Dify Tools / Health

| 端点 | 方法 | 说明 | 鉴权 |
|------|------|------|------|
| `/dashboard/summary` | GET | 仪表盘汇总数据 | JWT |
| `/dify/tools/nl2sql` | POST | Dify 工具：自然语言查询 | 公开（API Key） |
| `/dify/tools/create_report` | POST | Dify 工具：创建报告 | 公开（API Key） |
| `/dify/tools/approve_report` | POST | Dify 工具：审批报告 | 公开（API Key） |
| `/dify/tools/parse_document` | POST | Dify 工具：解析文档 | 公开（API Key） |
| `/health` | GET | 健康检查（liveness 基础） | 公开 |
| `/health/live` | GET | 存活探针 | 公开 |
| `/health/ready` | GET | 就绪探针 | 公开 |

## 4. 错误处理

业务错误通过 HTTP 状态码 + `detail` 字段返回：

```json
{
  "detail": "报告不存在"
}
```

限流与未捕获异常使用统一 `code` 字段的响应体：

```json
{ "code": 429, "message": "Too many requests" }
```

```json
{ "code": 500, "message": "Internal server error", "request_id": "uuid" }
```

请求体校验失败（FastAPI 默认 422）：

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

### 错误码约定

| `code` | 含义 | 触发场景 |
|--------|------|----------|
| 0 | 成功 | 正常业务响应 |
| 429 | 限流 | 请求超出速率限制（`RATE_LIMIT_ENABLED=true`） |
| 500 | 服务器错误 | 未捕获异常，由全局异常处理器统一返回并附带 `request_id` |

> 说明：资源不存在、参数非法、权限不足等业务错误以 HTTP 状态码（404 / 400 / 403 / 409 等）+ `detail` 文本描述返回，不使用自定义业务码，便于客户端按 HTTP 语义统一处理。

## 5. 限流

生产环境默认启用限流（`RATE_LIMIT_ENABLED=true`），基于 Redis 实现分布式速率限制。超限返回 429：

```json
{
  "code": 429,
  "message": "Too many requests"
}
```

## 6. Postman 集合

完整的请求示例见 [`financial-agent.postman_collection.json`](./financial-agent.postman_collection.json)，可导入 Postman 或 Bruno 直接调用。
