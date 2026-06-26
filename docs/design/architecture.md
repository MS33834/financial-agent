# 系统架构设计

## 1. 总体概述

企业级财务智能体采用**分层微服务架构**，核心目标是在本地或私有云环境中实现：

- PDF/Excel 财务文件上传与结构化解析
- 自然语言查询财务数据（NL2SQL）
- 利润表、资产负债表等报告自动生成
- 报告审批工作流与审计日志
- RBAC 权限控制与 ABAC 字段级加密

整体遵循"核心服务自包含、AI 能力可插拔"的原则：即使不连接 Dify/Ollama，系统也能以规则后端正常运行。

## 2. 架构图

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                              用户层                                       │
│   React + Vite 前端  ──►  Nginx 静态托管                                  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            API 网关层                                     │
│   FastAPI 后端 (backend/app/main.py)                                      │
│   - JWT 认证 / RBAC / ABAC                                                │
│   - 限流 / 安全头 / 审计中间件                                             │
│   - 健康检查 / Prometheus 指标                                             │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────┬───────────┼───────────┬───────────────┐
        ▼               ▼           ▼           ▼               ▼
┌──────────────┐ ┌──────────┐ ┌────────┐ ┌──────────┐ ┌──────────────┐
│  文档服务     │ │ 查询服务  │ │报告服务 │ │ 审批服务  │ │  审计服务     │
│ Documents    │ │ Queries  │ │Reports │ │Approvals │ │ Audit Logs   │
└──────────────┘ └──────────┘ └────────┘ └──────────┘ └──────────────┘
        │               │           │           │               │
        ▼               ▼           ▼           ▼               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          核心引擎层                                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │
│  │ PDF/Excel   │  │ Text2SQL    │  │ Report      │  │ Agent Runtime   │ │
│  │ Parser      │  │ (Rule/Vanna)│  │ Generator   │  │ (LangGraph)     │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
┌──────────────┐          ┌────────────────┐          ┌──────────────┐
│  PostgreSQL  │          │ Redis          │          │ MinIO        │
│  业务数据     │          │ 缓存/任务队列   │          │ 对象存储      │
└──────────────┘          └────────────────┘          └──────────────┘
        │                           │                           │
        ▼                           ▼                           ▼
┌──────────────┐          ┌────────────────┐          ┌──────────────┐
│  Celery      │          │ Ollama         │          │ Dify (可选)   │
│  Worker      │          │ 本地 LLM       │          │ 流程编排      │
└──────────────┘          └────────────────┘          └──────────────┘
```

## 3. 核心模块说明

| 模块 | 路径 | 职责 |
|------|------|------|
| 认证授权 | `app/routers/auth.py`, `app/security.py`, `app/core/abac.py` | JWT 登录、密码哈希、角色校验、基于属性的访问控制 |
| 文档解析 | `app/parser/`, `workers/` | PDF/Excel 上传、Mineru/OCR 解析、结构化清洗 |
| NL2SQL | `app/text2sql/` | 规则后端 + Vanna RAG 后端，SQL 沙箱白名单校验 |
| 报告生成 | `app/reporting/`, `app/services/report_service.py` | 利润表/资产负债表模板渲染、PDF/Excel 导出 |
| 审批流 | `app/services/approval_service.py`, `app/routers/approvals.py` | 报告状态机、多级审批、IM 通知 |
| 审计日志 | `app/services/audit_service.py`, `app/models/audit_log.py` | 全链路操作记录、不可篡改日志 |
| Agent 运行时 | `app/agent_runtime/` | LangGraph 状态机、意图识别、工具调用 |
| IM 集成 | `app/im/` | 钉钉/飞书/企业微信机器人接入 |
| 通知服务 | `notification/` | 邮件/IM/站内信多渠道通知，审批结果与异常告警推送 |
| RAG 检索 | `app/text2sql/`、`vanna_engine/` | Vanna + ChromaDB 向量检索，PostgreSQL 回退查询，NL2SQL 上下文增强 |

## 4. 数据流

### 4.1 文件上传 → 解析 → 入库

1. 用户通过前端上传 Excel/PDF
2. 后端接收文件并写入 MinIO
3. Celery Worker 异步调用解析器（Mineru 或本地解析）
4. 解析结果写入 `financial_reports` 表
5. 低置信度文件进入 `needs_review` 状态，等待人工复核

### 4.2 自然语言查询

1. 用户输入问题，如"2025 Q2 营业收入是多少？"
2. `intent.py` 识别查询意图
3. `Text2SQLBackend` 生成 SQL（优先 Vanna，失败降级规则后端）
4. `SQLSandbox` 校验 SQL 只允许 SELECT，禁止 DROP/DELETE/UPDATE
5. 执行 SQL 并返回结构化结果

### 4.3 报告生成与审批

1. 用户选择报告类型、年份、期间
2. 后端查询 `financial_reports` 生成报告内容
3. 报告进入 `reviewing` 状态
4. 审批人 approve/reject，状态流转并记录审计日志
5. 审批结果通过 IM 机器人通知

## 5. 安全设计

- **认证**：JWT access token，密码使用 bcrypt 哈希
- **授权**：RBAC（admin/finance_manager/auditor/viewer）+ ABAC 资源属性
- **字段加密**：`summary`、`attributes` 等敏感字段使用 AES-GCM 加密
- **SQL 注入防护**：参数化查询 + SQL 白名单 + 租户 ID 强制注入
- **限流**：基于 Redis 的请求速率限制
- **审计**：所有写操作记录审计日志

## 6. 部署视图

```text
                    ┌─────────────┐
                    │   Nginx     │
                    │   :3000     │
                    └──────┬──────┘
                           │
            ┌──────────────┼──────────────┐
            ▼              ▼              ▼
     ┌────────────┐ ┌────────────┐ ┌────────────┐
     │  Frontend  │ │  Backend   │ │  Worker    │
     │   :8080    │ │   :8000    │ │  (Celery)  │
     └────────────┘ └──────┬─────┘ └──────┬─────┘
                           │              │
        ┌──────────────────┼──────────────┤
        ▼                  ▼              ▼
 ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
 │ PostgreSQL   │  │ Redis        │  │ MinIO        │
 │   :5432      │  │   :6379      │  │   :9000      │
 └──────────────┘  └──────────────┘  └──────────────┘
        ▼
 ┌──────────────┐
 │ Ollama       │
 │   :11434     │
 └──────────────┘
```

生产环境建议：

- 使用外部托管 PostgreSQL/Redis/MinIO
- Ollama 独立部署在 GPU 服务器
- 后端多副本 + Nginx 负载均衡
- 使用 Kubernetes + Helm Chart（见 `deploy/helm/`）

## 7. 可扩展点

| 扩展方向 | 说明 |
|----------|------|
| 多租户隔离 | 所有业务表均包含 `tenant_id`，天然支持 |
| 模型切换 | `OLLAMA_MODEL`、`AGENT_LLM_MODEL` 可配置任意 Ollama 模型 |
| 接入 Dify | 通过 `DIFY_TOOL_API_KEY` 暴露工具 API 供 Dify 调用 |
| 更多数据源 | 扩展 `app/parser/` 下的解析器即可 |
| 审批流程自定义 | 在 `approval_service.py` 中扩展状态机 |

## 8. 模块边界与依赖关系

系统采用**分层依赖、单向调用**原则，禁止反向依赖与循环依赖，确保模块可独立演进与测试。

### 8.1 分层依赖规则

```text
前端 (frontend/src)
    │ HTTP / JSON
    ▼
API 层 (app/routers/*)        ← 仅做参数校验、鉴权、编排，不含业务逻辑
    │
    ▼
业务服务层 (app/services/*)    ← 领域逻辑、事务编排、状态机
    │
    ▼
引擎 / 适配层                  ← 文档解析、Text2SQL、报告渲染、Agent 运行时
 (app/parser/, app/text2sql/, app/reporting/, app/agent_runtime/, vanna_engine/)
    │
    ▼
数据访问层 (app/models/*, app/database.py)  ← ORM 模型与会话
    │
    ▼
基础设施 (PostgreSQL / Redis / MinIO / Ollama / Dify)
```

依赖方向自上而下：上层可依赖下层，下层不得反向引用上层。`routers` 不得被 `services` / `models` 反向导入。

### 8.2 模块依赖矩阵

| 模块 | 依赖上游（内部） | 依赖下游（基础设施） | 被谁调用 |
|------|------------------|----------------------|----------|
| Auth | security、models/user | PostgreSQL | 前端、所有需鉴权的路由 |
| Documents | services/document_service、storage | PostgreSQL、MinIO、Celery | 前端、Dify Tools |
| Queries (NL2SQL) | text2sql、vanna_engine、sql_sandbox | PostgreSQL、Ollama | 前端、Agent、Dify Tools |
| Reports | services/report_service、reporting | PostgreSQL、MinIO | 前端、Dify Tools |
| Approvals | services/approval_service、notification | PostgreSQL、Redis | 前端、IM |
| Agent | agent_runtime、text2sql、reporting | PostgreSQL、Ollama、Redis | 前端 |
| Notification | notification/channels | SMTP、IM Webhook、PostgreSQL | Approvals、Worker、审计告警 |
| Audit | services/audit_service、models/audit_log | PostgreSQL | 所有写操作（中间件织入） |
| Worker (Celery) | services/*、shared | PostgreSQL、Redis、MinIO | 被路由通过任务队列触发 |

### 8.3 共享契约

- `shared/` 模块提供跨进程的**纯数据契约**（`constants.py` 枚举、`events.py` 事件定义、`schemas.py` Pydantic 模型），不含业务逻辑，可被 `backend` 与 `workers` 同时导入，避免事件 / 状态语义在两端漂移。
- 事件主题（`EVENT_TOPIC_*`）统一在 `shared/constants.py` 定义，作为消息总线的寻址契约。

### 8.4 边界约束

- **API 层无状态**：`routers` 不持有可变状态，所有状态写入数据库或 Redis。
- **引擎层可替换**：`Text2SQL`（规则 / Vanna）、`LLM`（Ollama / Dify）、`Storage`（MinIO / 本地）均通过抽象后端切换，业务服务层不感知具体实现。
- **审计无侵入**：审计日志通过中间件 / 装饰器织入，业务模块无需显式调用即可记录关键写操作。

## 9. 技术选型说明

| 技术 | 选型理由 |
|------|----------|
| **FastAPI** | 原生 async、自动生成交互式 OpenAPI 文档（`/docs`）、Pydantic 校验与统一响应模型天然契合；性能足以支撑财务报告类中低并发场景，开发效率高。 |
| **SQLAlchemy 2.0** | 成熟的 ORM，支持类型化查询与同步 / 异步引擎；与 Alembic 配合实现可审计的数据库迁移；多租户场景下通过 `tenant_id` 过滤器统一注入。 |
| **Celery** | 文档解析、报告生成等重计算任务需异步化以避免阻塞 API；Celery 配合 Redis broker 提供任务重试、优先级与监控；独立 Worker 进程便于水平扩缩容与优雅关闭。 |
| **Dify（可选）** | 提供可视化 LLM 应用编排与工具调用流程，降低非开发人员调整 Agent 流程的门槛；通过 `/api/v1/dify/tools/*` 暴露内部能力（NL2SQL、建报告、审批）供 Dify 编排，做到"接入即增强、不接入系统仍可用规则后端"。 |
| **Ollama（本地 LLM）** | 私有化部署刚需：财务数据敏感，禁止外发第三方 LLM；Ollama 支持本地运行开源模型，零数据外泄，配合 `OLLAMA_MODEL` 可灵活切换模型规模。 |

补充选型：

- **PostgreSQL**：金融场景对事务一致性要求高，JSONB + 行级安全适合结构化与半结构化财务数据。
- **Redis**：缓存、分布式限流、Celery broker 复用，降低组件数量。
- **MinIO**：S3 兼容的对象存储，私有化部署原始财务文件，满足合规留存要求。
- **LangGraph**：Agent 运行时以显式状态机建模多轮对话与工具调用，便于错误恢复与可观测。

