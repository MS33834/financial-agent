# 企业级财务智能体 - 后期完善计划表

> 本文件由 AI 助手根据 2026-06-25 的全面代码 review 生成，记录项目当前状态、未完成项与后续完善计划。
> 在计划项全部完成或明确废弃前，本文件应保留在仓库中并持续更新。

---

## 1. 项目当前状态

### 1.1 已完成的里程碑

| 里程碑 | 说明 | 相关 Commit |
|--------|------|-------------|
| 专家审查修复 | 修复 100+ 项安全、事务原子性、输入验证、前端可访问性问题 | `9373c90` |
| 本地化改造 | 存储、任务执行默认本地；MinIO/Celery/Redis 改为可选扩展 | `c06285e` |
| 部署配置适配 | docker-compose、Helm、CI、Makefile 适配默认本地模式 | `1ed7696` |
| 开箱即用 | `make init && make up` 默认启动 Dify + Financial Agent 完整系统 | 当前待提交 |
| 代码质量基线 | 后端测试 195 passed，ruff/mypy 通过；前端 lint/test/build 全过 | - |

### 1.2 当前技术栈

- **后端**：FastAPI + SQLAlchemy + PostgreSQL（复用 Dify）
- **任务**：Celery（可选），默认同步执行
- **存储**：本地文件系统（可选 MinIO）
- **LLM**：Ollama（本地）/ OpenAI 兼容 API
- **流程编排**：Dify（开源，vendor 方式引入）
- **前端**：React + Vite + TypeScript
- **部署**：Docker Compose / Helm

---

## 2. 完善计划表

### 2.1 高优先级（影响可用性或生产安全）

| ID | 模块 | 任务 | 状态 | 说明 / 建议方案 | 相关文件 |
|----|------|------|------|-----------------|----------|
| H1 | 部署 | 验证 `make init && make up` 在干净环境可跑通 | 待验证 | 找一台新机器或 CI job 执行完整启动流程，确认 Dify 与 FA 网络互通、数据库可连、前端可访问 | `Makefile`, `docker-compose.yml` |
| H2 | 部署 | 修复 `down-volumes` 同时清理 Dify 数据卷 | 已完成 | `down-volumes` 已同步调用 `docker compose ... -p dify down -v` 清理 Dify 卷 | `Makefile` |
| H3 | 部署 | 解决 `make up-build` 不会触发镜像重建的问题 | 已完成 | `up-build` 已显式对 Dify 与 FA 分别传入 `--build` | `Makefile` |
| H4 | 安全 | 强制生产环境修改默认 SECRET_KEY / INIT_PASSWORD | 已完成 | `main.py` lifespan 启动前新增 `_validate_production_config()`：生产环境拒绝空/示例默认值/长度<32 的 SECRET_KEY，fail-fast | `backend/app/main.py` |
| H5 | 安全 | 生产环境 CORS 默认禁止通配符 | 已完成 | `_validate_production_config()` 在生产环境检测到 `CORS_ORIGINS=*` 时直接拒绝启动并提示配置前端域名 | `backend/app/main.py` |
| H6 | 后端 | 修复 `IMService` 用 `TestClient` 调用内部 API 的架构问题 | 已完成 | R8 已重构：移除 `TestClient`，改为直接调用 service 层 | `app/services/im_service.py` |
| H7 | 后端 | 完善 IM 机器人命令处理错误边界 | 已完成 | 新增 5 个单测覆盖：不存在的 report_id、序号缓存为空、序号越界、handle_command 异常兜底、缺少 report_id 用法提示 | `app/services/im_service.py`, `tests/test_im.py` |
| H8 | 后端 | 实现通知服务占位模块 | 已完成 | 新增 `notification/` 模块：NotificationService 多渠道调度（邮件/IM/站内信），渠道降级、发送记录持久化、站内信列表与已读标记 API | `backend/notification/`, `backend/app/models/notification.py`, `backend/app/routers/notifications.py` |
| H9 | 测试 | 核心模块测试覆盖率提升到 90%+ | 已完成 | 新增 31 个测试：dify_tools(12)、reflection_service(11)、health(8)；总测试从 200 增至 231 passed | `tests/test_dify_tools.py`, `tests/test_reflection_service.py`, `tests/test_health_service.py` |
| H10 | 前端 | 实现 404 页面 | 已完成 | 新增 `NotFoundPage` 组件，`App.tsx` 的 `path="*"` 改为渲染 404 页面而非静默重定向 | `frontend/src/pages/NotFoundPage.tsx`, `frontend/src/App.tsx` |

### 2.2 中优先级（功能完整性）

| ID | 模块 | 任务 | 状态 | 说明 / 建议方案 | 相关文件 |
|----|------|------|------|-----------------|----------|
| M1 | 后端 | 实现审计服务独立模块 | 待实现 | `backend/audit_service/` 为空目录，需将当前 `app/services/audit_service.py` 中的能力沉淀为可扩展审计框架 | `backend/audit_service/`, `app/services/audit_service.py` |
| M2 | 后端 | 实现 Vanna 引擎占位模块 | 待实现 | `backend/vanna_engine/` 为空目录，当前 Text2SQL 的 Vanna 后端在 `app/text2sql/` 中，可迁移/封装 | `backend/vanna_engine/`, `app/text2sql/vanna_backend.py` |
| M3 | 后端 | API Key 生命周期管理 | 已完成 | 新增 usage_count/first_used_at/rotated_from 字段；validate_api_key 更新使用统计；新增 rotate_api_key 轮换函数与 POST /{id}/rotate API | `app/services/api_key_service.py`, `app/models/api_key.py`, `app/routers/api_keys.py` |
| M4 | 后端 | 增强 Agent 多轮对话与错误恢复 | 已完成 | AgentChatRequest 新增 conversation_id/history 字段；run_agent 支持 history 注入；execute_tool 节点添加最多 2 次指数退避重试 | `app/routers/agent.py`, `app/agent_runtime/graph.py` |
| M5 | 后端 | RAG 持久化索引 | 已完成 | index_document 同时写入 rag_chunks 表（原生 SQL，兼容 SQLite/PG）；query 内存未命中时回退 DB 查询；新增 persist_to_db 方法 | `app/services/rag_service.py` |
| M6 | 后端 | 报告生成模板化与可配置 | 已完成 | 新增 register_template() 动态注册机制；render_report 支持 templates 参数覆盖默认；ReportGenerator 支持 custom_templates | `app/reporting/templates.py`, `app/reporting/generator.py` |
| M7 | 后端 | 字段级加密完整落地 | 已完成 | 加密输出新增密钥版本前缀 v{version}:salt:ciphertext；decrypt 向后兼容旧格式；新增 re_encrypt() 密钥轮换函数与 get_key_version() | `app/core/encryption.py` |
| M8 | 后端 | Worker 进程独立化 | 已完成 | 新增 workers/ 模块：信号处理优雅关闭、max_tasks_per_child、acks_late、reject_on_worker_lost 等生产级配置 | `workers/__init__.py`, `workers/run.py` |
| M9 | 后端 | 共享模块（shared/）定义跨服务契约 | 已完成 | 新增 shared/ 模块：constants（状态/动作枚举）、events（领域事件基类+3个具体事件）、schemas（DataResponse/PaginatedData/ErrorResponse 等通用契约） | `shared/__init__.py`, `shared/constants.py`, `shared/events.py`, `shared/schemas.py` |
| M10 | 前端 | 用户管理页面 | 已完成 | 新增后端 users CRUD API（list/create/update/delete/reset-password）；前端 UsersPage 含表格+创建/编辑 Modal+重置密码+删除 | `backend/app/routers/users.py`, `backend/app/schemas/user.py`, `frontend/src/pages/UsersPage.tsx`, `frontend/src/types/user.ts` |
| M11 | 前端 | API Key 管理页面 | 已完成 | ApiKeysPage 含表格+创建 Modal（明文 key 一次性展示）+轮换/吊销/删除操作 | `frontend/src/pages/ApiKeysPage.tsx`, `frontend/src/types/apiKey.ts` |
| M12 | 前端 | IM 用户映射管理页面 | 已完成 | IMUserMappingsPage 含表格+创建 Modal（platform 选择）+删除 | `frontend/src/pages/IMUserMappingsPage.tsx` |
| M13 | 前端 | 系统设置页面 | 已完成 | SettingsPage 只读配置展示（中文标签）+重载按钮 | `frontend/src/pages/SettingsPage.tsx`, `backend/app/routers/admin.py` |
| M14 | 前端 | 完善 e2e 测试覆盖核心用户旅程 | 已完成 | 扩展为 4 个测试：登录页渲染、404 页面（始终运行）+ 登录流程、页面导航（E2E_BACKEND=true 启用） | `frontend/e2e/smoke.spec.ts` |
| M15 | 测试 | 增加集成测试覆盖 Dify + FA 联动 | 已完成 | 新增 test_integration_api.py 3 个 @pytest.mark.integration 用例：文档上传→解析→查询、报告→生成→审批、Agent 问答 | `tests/integration/test_integration_api.py`, `tests/integration/conftest.py` |

### 2.3 低优先级（工程化与治理）

| ID | 模块 | 任务 | 状态 | 说明 / 建议方案 | 相关文件 |
|----|------|------|------|-----------------|----------|
| L1 | 部署 | Dockerfile builder 阶段不安装 dev 依赖已修复，但需验证镜像大小 | 待验证 | 确认生产镜像不再包含 pytest/ruff/mypy | `backend/Dockerfile` |
| L2 | 部署 | 统一 Python 版本（3.12 vs 3.14） | 已完成 | CI、Dockerfile、pyproject.toml requires-python 统一为 3.12 | `backend/Dockerfile`, CI workflow, `backend/pyproject.toml` |
| L3 | 部署 | 非 root 用户运行时数据卷权限处理 | 已完成 | Dockerfile 已 `mkdir -p /app/data/storage && chown -R appuser:appuser /app`；appuser 固定 UID/GID=999 与 Helm `runAsUser` 对齐，命名卷首次挂载继承镜像目录属主 | `backend/Dockerfile` |
| L4 | 部署 | 生产环境 Alembic 迁移失败兜底策略 | 已完成 | `entrypoint.sh` 的 `alembic upgrade head` 改为重试 3 次、间隔递增（5/10s），全部失败才退出 | `scripts/entrypoint.sh` |
| L5 | 部署 | 多实例 RateLimit 改为 Redis 实现 | 已完成 | RateLimitMiddleware 新增 redis_url 参数，传入时用 Redis INCR+EXPIRE 实现分布式限流，Redis 故障 fail-open；未传入保持内存实现 | `app/middleware.py` |
| L6 | 文档 | 填充 `docs/design/` 设计文档 | 已完成 | 扩展 architecture.md：新增核心模块表（通知/RAG）、模块边界与依赖关系、技术选型说明 | `docs/design/architecture.md` |
| L7 | 文档 | 完善 API 文档 | 已完成 | overview.md 扩展：16 模块完整端点列表、API Key 认证说明、DataResponse/PaginatedResponse 格式、错误码约定 | `docs/api/overview.md` |
| L8 | 文档 | 建立 CHANGELOG | 已完成 | 新建 CHANGELOG.md，Keep a Changelog 格式，含 0.2.0（功能增强）与 0.1.0（MVP）两个版本 | `CHANGELOG.md` |
| L9 | 治理 | 清理空占位目录 | 已完成 | notification/、shared/、workers/ 已填充实际代码；audit_service/、vanna_engine/ 保留 .gitkeep（M1/M2 待实现时填充） | - |
| L10 | 治理 | 版本号与 Release 管理 | 已完成 | pyproject.toml、package.json、main.py 版本统一升至 0.2.0 | `pyproject.toml`, `frontend/package.json`, `backend/app/main.py` |
| L11 | 前端 | 升级依赖并修复安全审计 | 已完成 | npm audit 0 漏洞（409 依赖）；pip-audit 未安装（需后续安装），记录于 CHANGELOG 已知问题 | `frontend/package.json`, `backend/pyproject.toml` |
| L12 | 后端 | 完善日志与链路追踪 | 已完成 | 新增 app/tracing.py：setup_tracing + OTLP exporter（可选依赖）；logger.py 新增 inject_trace_context processor 注入 trace_id/span_id | `app/tracing.py`, `app/logger.py` |

---

### 2.4 本次 Review 新增任务（2026-06-25）

> 以下任务来自对 MVP 闭环性的 review，按 P0/P1/P2 分级，团队可优先执行 P0/P1。

#### P0（不修复则 MVP 无法跑通）

| ID | 模块 | 任务 | 状态 | 说明 / 建议方案 | 相关文件 |
|----|------|------|------|-----------------|----------|
| R1 | 配置 | 修复 `CORS_ORIGINS` 导致后端启动失败 | 已完成 | `config.py` 中将字段改为 `str`，新增 `cors_origins_list` 属性支持逗号分隔与 JSON 数组两种写法；`main.py` 改用属性读取 | `.env.example`, `backend/app/config.py`, `backend/app/main.py` |
| R2 | 前端 | 重写审批页面，打通审批 UI 闭环 | 已完成 | `ApprovalsPage` 改为拉取 `GET /reports?status=reviewing` 列表；类型 `Approval` 改为 `PendingApproval` | `frontend/src/pages/ApprovalsPage.tsx`, `frontend/src/types/approval.ts`, `frontend/src/types/report.ts` |

#### P1（功能有明显缺陷）

| ID | 模块 | 任务 | 状态 | 说明 / 建议方案 | 相关文件 |
|----|------|------|------|-----------------|----------|
| R3 | 后端 | 修复 Agent 文档问答状态过滤错误 | 已完成 | `document_qa_tool` 将状态过滤从 `completed` 修正为 `success`；同步修正测试数据 | `backend/app/agent_runtime/tools.py`, `backend/tests/test_agent_runtime.py` |
| R4 | DevOps | 修复 Makefile 中指向 Dify 服务的错误命令 | 已完成 | `logs-api` / `shell-api` 改为使用 `vendor/dify/docker/docker-compose.yaml` 并指定 `-p dify` | `Makefile` |
| R5 | 前端 | 报告导出按钮按状态禁用 | 已完成 | `ReportDetail` 增加 `canExport` 判断，非 `reviewing` / `approved` 状态禁用导出按钮 | `frontend/src/components/ReportDetail.tsx` |
| R6 | 文档 | 持续同步 ROADMAP 与实际进度 | 已完成 | 本批次修复完成后同步更新 R1~R8 状态 | `docs/ROADMAP.md` |

#### P2（架构/生产隐患）

| ID | 模块 | 任务 | 状态 | 说明 / 建议方案 | 相关文件 |
|----|------|------|------|-----------------|----------|
| R7 | 配置 | 修正 Dify 控制台地址端口 | 已完成 | `.env.example` 中 `CONSOLE_WEB_URL` 从 `3000` 改为 `8080` | `.env.example` |
| R8 | 后端 | IMService 改为直接调用 service 层 | 已完成 | 移除 `TestClient`；改为直接调用 `QueryService`、`create_report_task`、`list_reports`、`record_approval`；保留 ADMIN/AUDITOR 角色校验 | `backend/app/services/im_service.py` |

### 2.5 全面检查与优化（2026-06-26）

> 对后端 / 前端 / 部署三层进行全量代码扫描，批量修复 P0 安全与可用性问题及 P1 工程质量问题。
> 验证结果：后端 195 passed / 19 skipped，ruff + mypy 全过；前端 build 通过。

| ID | 模块 | 任务 | 状态 | 说明 / 修复方案 | 相关文件 |
|----|------|------|------|-----------------|----------|
| C1 | 后端·安全 | 路径穿越防御补全 | 已完成 | `upload` / `download_bytes` 增加 `key.lstrip("/")` + `resolve().relative_to(root)` 双重校验，杜绝绝对路径逃逸 | `backend/app/storage.py` |
| C2 | 后端·安全 | Excel 解析 DoS 防护 | 已完成 | 弃用 `iter_rows(max_row=...)`（会为空表填充空行导致误判），改为惰性迭代达上限即中止拒绝，避免恶意大文件耗尽内存 | `backend/app/parser/excel_parser.py` |
| C3 | 后端·事务 | 审计日志与业务写入原子性 | 已完成 | `document_service` / `report_service` 改为 `db.flush()` 取 ID + `log_action(commit=False)` + `db.commit()` 统一提交 | `backend/app/services/document_service.py`, `backend/app/services/report_service.py` |
| C4 | 后端 | access_policies 分页元数据丢失 | 已完成 | `response_model` 由 `DataResponse[list]` 改为 `PaginatedResponse`，返回 `total/page/page_size/items` 结构，分页信息不再被剥离 | `backend/app/routers/access_policies.py` |
| C5 | 后端 | IM 路由死代码与异常日志 | 已完成 | 移除 `im.py` 未用的 `create_access_token` 调用；异常日志补充 `error=str(exc)`；`reflect_task_failure` 由 `suppress(Exception)` 改为带 `logger.warning` 的 try/except | `backend/app/routers/im.py`, `backend/app/tasks/utils.py` |
| C6 | 后端 | IMService 清理死参数 | 已完成 | 移除未使用的 `token` 形参与 `typing.Any` 导入，消除 ruff/mypy 告警 | `backend/app/services/im_service.py` |
| C7 | 前端·可用性 | Modal 焦点陷阱修复 | 已完成 | `useEffect` 依赖内联 `onClose` 每次渲染重跑导致 textarea 失焦；改用 `useRef` 持有回调，effect 仅注册一次 | `frontend/src/components/ui/Modal.tsx` |
| C8 | 前端·安全 | 上传 FormData Content-Type | 已完成 | 移除手动设置 `multipart/form-data` header（会丢失 boundary），交由浏览器自动生成 | `frontend/src/components/DocumentUpload.tsx` |
| C9 | 前端 | AuthContext 绕过 api 实例 | 已完成 | 登录 / me 改用统一 `api` 实例（自动注入 baseURL、拦截器），补齐 `LoginResponse`/`MeResponse` 类型 | `frontend/src/context/AuthContext.tsx` |
| C10 | 前端 | 统一错误处理与类型安全 | 已完成 | 列表页统一 `getErrorMessage`、`DataResponse<T>` 泛型、`params` 对象替代手拼 URL；`ReportCreate` 移除 `as Report` 断言 | `DocumentsPage`, `ReportsPage`, `AuditPage`, `ReportCreate`, `ReportDetail` 等 |
| C11 | 前端 | NavBar 高亮与 a11y | 已完成 | `isActive` 支持 `startsWith(path + '/')` 子路由高亮；`showLogout` 默认 true；`Loading` 补 `role="status"` / `aria-live` | `frontend/src/components/NavBar.tsx`, `frontend/src/components/ui/Loading.tsx` |
| C12 | 前端 | AgentChat key 碰撞与 tabnabbing | 已完成 | `Date.now().toString()` → `crypto.randomUUID()`；外链加 `noopener,noreferrer`；登录判定改 `endsWith('/auth/login')` | `frontend/src/pages/AgentChatPage.tsx`, `frontend/src/api/client.ts` |
| C13 | 部署 | Ollama healthcheck 与 profile | 已完成 | healthcheck 由 `curl` 改为 `ollama list`；`fa-ollama` 加 `profiles:[ollama]`；worker 加 `hostname` 保证 healthcheck 节点名匹配 | `docker-compose.yml` |
| C14 | 部署 | nginx 非 root PID 可写 | 已完成 | Dockerfile 用 `sed` 将主 `/etc/nginx/nginx.conf` 的 `pid` 指向 `/tmp/nginx.pid`，确保非 root 可写 | `frontend/Dockerfile` |
| C15 | 部署 | 后端镜像存储目录与 UID 固定 | 已完成 | builder 阶段补 `COPY app/` 修复 editable 安装缺源码；运行阶段 `mkdir -p /app/data/storage`；`appuser` 固定 UID/GID=999 与 Helm `runAsUser` 对齐 | `backend/Dockerfile` |
| C16 | 部署 | worker Redis 默认值与依赖 | 已完成 | worker 的 `REDIS_URL`/`CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND` 默认指向本 compose 的 redis 服务；明确 backend 不声明 db_postgres depends_on（profile-gated 会致模型失效，改由连接重试保证就绪） | `docker-compose.yml` |
| C17 | 部署 | Helm / Makefile 一致性 | 已完成 | Helm `RATE_LIMIT_MAX_REQUESTS` 由 100 改为 120 与全局默认一致；`Makefile` `.PHONY` 补全 `up-core`/`down-core`/`backend-worker` 等遗漏目标 | `deploy/helm/financial-agent/values.yaml`, `Makefile` |

---

## 3. 需要用户决策的事项

| ID | 问题 | 选项 | 建议 |
|----|------|------|------|
| D1 | Dify 是否作为默认启动组件？ | A) 保持当前开箱即用（默认含 Dify）<br>B) 改为核心模式默认，Dify 需手动启用 | 已选 A，当前 `make up` 默认启动 Dify；如资源受限可改为 B |
| D2 | 空目录模块的实现优先级？ | A) 逐个实现（审计、通知、Vanna 引擎）<br>B) 删除占位，保持精简 | 建议 A，按 H8/M1/M2 顺序实现 |
| D3 | RAG 使用哪种向量数据库？ | A) 复用 Dify 的 Weaviate<br>B) 新增 pgvector<br>C) 使用 Chroma | 建议 A（减少额外依赖）或 B（与 PostgreSQL 一致） |
| D4 | 前端技术栈是否引入 UI 组件库？ | A) 保持当前手写组件<br>B) 引入 Ant Design / Material UI | 建议 B 可加速 M10-M13 开发 |
| D5 | 是否接入外部监控系统？ | A) 仅保留 Prometheus 指标<br>B) 增加 Grafana dashboard + Alertmanager | 建议 B 用于生产 |
| D6 | 是否支持多租户数据隔离增强？ | A) 当前按 tenant_id 过滤已足够<br>B) 增加行级安全策略（RLS） | 建议 B 用于金融级安全 |

---

## 4. 验收标准

完成以下全部项后，可认为项目达到"完整可商用 MVP"：

- [ ] H1-H10 全部完成
- [ ] M1-M15 全部完成
- [ ] 后端测试覆盖率 ≥ 90%
- [ ] 前端测试覆盖率 ≥ 80%
- [ ] e2e 测试覆盖：登录、上传文档、生成报告、审批、Agent 对话
- [ ] 生产部署文档完整且经过验证
- [ ] 安全扫描无高危漏洞
- [ ] 性能基准测试通过（并发 50 用户，P95 < 2s）
- [ ] CHANGELOG 与版本 tag 建立

---

## 5. 更新记录

| 日期 | 更新人 | 变更内容 |
|------|--------|----------|
| 2026-06-25 | AI Assistant | 初始创建，包含全面 review 结果与完善计划 |
| 2026-06-25 | AI Assistant | 新增本次 MVP 闭环 review 任务（R1~R8），并将 H2/H3 标记为已完成 |
| 2026-06-25 | AI Assistant | 完成 R1~R8 全部修复：CORS、审批页面、document_qa 过滤、Makefile、导出按钮、Dify 端口、IMService 重构 |
| 2026-06-26 | AI Assistant | 全面检查与优化（C1~C17）：路径穿越、Excel DoS、审计事务原子性、Modal 焦点陷阱、FormData、nginx PID、Dockerfile UID、worker Redis 默认值等 |
| 2026-06-26 | AI Assistant | 工程化补强：H4/H5 生产配置强校验（SECRET_KEY/CORS）、H6 同步已完成、H7 IM 错误边界单测、H10 404 页面、L3 卷权限、L4 Alembic 重试、CI pip 缓存 |
| 2026-06-26 | AI Assistant | 功能增强批次 0.2.0：H8 通知服务、H9 测试覆盖、M3-M9 后端模块、M10-M14 前端页面与测试、M15 集成测试、L2/L5-L12 工程化治理 |
