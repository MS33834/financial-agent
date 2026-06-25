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
| H4 | 安全 | 强制生产环境修改默认 SECRET_KEY / INIT_PASSWORD | 待实现 | 在 `scripts/bootstrap.py` 或 entrypoint 中增加校验，禁止用户使用示例弱密钥启动 production | `scripts/bootstrap.py`, `scripts/entrypoint.sh` |
| H5 | 安全 | 生产环境 CORS 默认禁止通配符 | 待实现 | 当前代码在 `CORS_ORIGINS=*` 时禁用 credentials，但建议 production 直接拒绝启动并提示 | `app/main.py` |
| H6 | 后端 | 修复 `IMService` 用 `TestClient` 调用内部 API 的架构问题 | 待重构 | MVP 注释已说明应改为直接调用 service 层；当前方式耦合 FastAPI 测试客户端，生产环境不推荐 | `app/services/im_service.py` |
| H7 | 后端 | 完善 IM 机器人命令处理错误边界 | 待实现 | `im_service.py` 多处错误处理分支未覆盖，需补充单元测试 | `app/services/im_service.py`, `tests/test_im.py` |
| H8 | 后端 | 实现通知服务占位模块 | 待实现 | `backend/notification/` 为空目录，需实现邮件/IM/站内信通知能力 | `backend/notification/` |
| H9 | 测试 | 核心模块测试覆盖率提升到 90%+ | 待实现 | 重点覆盖 `dify_tools.py` (53%)、`health.py` (59%)、`reflection_service.py` (54%)、`report_service.py` (79%) | `tests/` |
| H10 | 前端 | 实现 404 页面 | 待实现 | 当前 `path="*"` 直接重定向到 dashboard | `frontend/src/App.tsx` |

### 2.2 中优先级（功能完整性）

| ID | 模块 | 任务 | 状态 | 说明 / 建议方案 | 相关文件 |
|----|------|------|------|-----------------|----------|
| M1 | 后端 | 实现审计服务独立模块 | 待实现 | `backend/audit_service/` 为空目录，需将当前 `app/services/audit_service.py` 中的能力沉淀为可扩展审计框架 | `backend/audit_service/`, `app/services/audit_service.py` |
| M2 | 后端 | 实现 Vanna 引擎占位模块 | 待实现 | `backend/vanna_engine/` 为空目录，当前 Text2SQL 的 Vanna 后端在 `app/text2sql/` 中，可迁移/封装 | `backend/vanna_engine/`, `app/text2sql/vanna_backend.py` |
| M3 | 后端 | API Key 生命周期管理 | 待实现 | 增加过期时间、禁用/启用状态、使用统计、轮换机制 | `app/services/api_key_service.py`, `app/models/api_key.py` |
| M4 | 后端 | 增强 Agent 多轮对话与错误恢复 | 待实现 | `app/routers/agent.py` 仅 1 个端点；LangGraph 需支持对话历史、工具调用失败重试、长任务状态查询 | `app/routers/agent.py`, `app/agent_runtime/` |
| M5 | 后端 | RAG 持久化索引 | 待实现 | 当前 `app/services/rag_service.py` 为内存索引，单节点且重启丢失；建议接入向量数据库（Weaviate/pgvector/Chroma） | `app/services/rag_service.py` |
| M6 | 后端 | 报告生成模板化与可配置 | 待实现 | `app/reporting/templates.py` 可能已有基础，需支持自定义模板、多格式导出、邮件订阅 | `app/reporting/` |
| M7 | 后端 | 字段级加密完整落地 | 待实现 | `app/core/encryption.py` 已实现算法，但需确认哪些字段真正启用加密，并补充迁移脚本 | `app/core/encryption.py`, `app/models/` |
| M8 | 后端 | Worker 进程独立化 | 待实现 | `workers/` 为空目录；当 `TASK_BACKEND=celery` 时，应支持独立 worker 容器/进程并完善监控 | `workers/`, `backend/scripts/worker.py` |
| M9 | 后端 | 共享模块（shared/）定义跨服务契约 | 待实现 | `shared/` 为空目录，可放置共享的 schemas、events、constants | `shared/` |
| M10 | 前端 | 用户管理页面 | 待实现 | 缺少租户/用户 CRUD 页面，当前只能通过 API 或数据库管理 | `frontend/src/pages/` |
| M11 | 前端 | API Key 管理页面 | 待实现 | 前端无 API Key 创建/查看/删除界面 | `frontend/src/pages/` |
| M12 | 前端 | IM 用户映射管理页面 | 待实现 | 已有后端 API，但前端无对应页面 | `frontend/src/pages/`, `app/routers/im_user_mappings.py` |
| M13 | 前端 | 系统设置页面 | 待实现 | 包括存储后端、任务后端、LLM 配置、通知配置等可视化配置 | `frontend/src/pages/` |
| M14 | 前端 | 完善 e2e 测试覆盖核心用户旅程 | 待实现 | 当前仅 `frontend/e2e/smoke.spec.ts` 一个 smoke 测试 | `frontend/e2e/` |
| M15 | 测试 | 增加集成测试覆盖 Dify + FA 联动 | 待实现 | 当前 `tests/integration/` 只有存储集成测试 | `tests/integration/` |

### 2.3 低优先级（工程化与治理）

| ID | 模块 | 任务 | 状态 | 说明 / 建议方案 | 相关文件 |
|----|------|------|------|-----------------|----------|
| L1 | 部署 | Dockerfile builder 阶段不安装 dev 依赖已修复，但需验证镜像大小 | 待验证 | 确认生产镜像不再包含 pytest/ruff/mypy | `backend/Dockerfile` |
| L2 | 部署 | 统一 Python 版本（3.12 vs 3.14） | 待决策 | CI/本地使用 3.14，Dockerfile 用 3.12，建议明确支持矩阵 | `backend/Dockerfile`, CI workflow |
| L3 | 部署 | 非 root 用户运行时数据卷权限处理 | 待实现 | `USER appuser` 运行，挂载卷可能因 UID 不一致导致写入失败 | `backend/Dockerfile`, `scripts/entrypoint.sh` |
| L4 | 部署 | 生产环境 Alembic 迁移失败兜底策略 | 待实现 | 当前 `alembic upgrade head` 失败直接退出，建议增加重试或健康检查 | `scripts/entrypoint.sh` |
| L5 | 部署 | 多实例 RateLimit 改为 Redis 实现 | 待实现 | 当前内存实现无法跨实例共享；当启用 Redis 时可切换 | `app/middleware.py` |
| L6 | 文档 | 填充 `docs/design/` 设计文档 | 待实现 | 当前为空目录，需补充架构图、数据流、模块边界 | `docs/design/` |
| L7 | 文档 | 完善 API 文档 | 待实现 | `docs/api/overview.md` 内容较简单，可接入 OpenAPI/Swagger 导出 | `docs/api/` |
| L8 | 文档 | 建立 CHANGELOG | 待实现 | 当前无版本变更记录，建议按 Semantic Versioning 维护 | `CHANGELOG.md` |
| L9 | 治理 | 清理空占位目录 | 待决策 | 若短期内不实现，可保留 `.gitkeep`；若长期不实现，建议删除避免误导 | `backend/audit_service/`, `backend/notification/`, `backend/vanna_engine/`, `shared/`, `workers/`, `docs/design/` |
| L10 | 治理 | 版本号与 Release 管理 | 待实现 | 当前 `0.1.0`，建议达到稳定后打 tag 并发布 release | `pyproject.toml`, `frontend/package.json` |
| L11 | 前端 | 升级依赖并修复安全审计 | 待实现 | 定期 `npm audit` / `pip audit`，更新过期依赖 | `frontend/package.json`, `backend/pyproject.toml` |
| L12 | 后端 | 完善日志与链路追踪 | 待实现 | 当前已有 request_id，但可补充 OpenTelemetry/Jaeger 集成 | `app/logger.py`, `app/main.py` |

---

### 2.4 本次 Review 新增任务（2026-06-25）

> 以下任务来自对 MVP 闭环性的 review，按 P0/P1/P2 分级，团队可优先执行 P0/P1。

#### P0（不修复则 MVP 无法跑通）

| ID | 模块 | 任务 | 状态 | 说明 / 建议方案 | 相关文件 |
|----|------|------|------|-----------------|----------|
| R1 | 配置 | 修复 `CORS_ORIGINS` 导致后端启动失败 | 待修复 | `.env.example` 中逗号分隔字符串无法被 Pydantic `list[str]` 解析；建议改为 JSON 数组或在 `config.py` 增加 comma-split validator | `.env.example`, `backend/app/config.py` |
| R2 | 前端 | 重写审批页面，打通审批 UI 闭环 | 待修复 | 当前页面拉取的是审批历史记录，且字段与后端不匹配；应改为拉取 `GET /reports?status=reviewing` 列表并执行审批操作 | `frontend/src/pages/ApprovalsPage.tsx`, `frontend/src/types/approval.ts` |

#### P1（功能有明显缺陷）

| ID | 模块 | 任务 | 状态 | 说明 / 建议方案 | 相关文件 |
|----|------|------|------|-----------------|----------|
| R3 | 后端 | 修复 Agent 文档问答状态过滤错误 | 待修复 | `document_qa_tool` 使用 `status.in_({"completed", ...})`，但 Document 状态无 `completed`，应为 `success` | `backend/app/agent_runtime/tools.py` |
| R4 | DevOps | 修复 Makefile 中指向 Dify 服务的错误命令 | 待修复 | `logs-api` / `shell-api` 在 FA compose 中找不到 `api` 服务，应指定 Dify compose 文件路径 | `Makefile` |
| R5 | 前端 | 报告导出按钮按状态禁用 | 待修复 | 后端仅允许 `reviewing` / `approved` 状态导出，前端应在其他状态禁用导出按钮 | `frontend/src/components/ReportDetail.tsx` |
| R6 | 文档 | 持续同步 ROADMAP 与实际进度 | 进行中 | 本次已将 H2/H3 标记为完成；后续修复完 R1~R5 后需同步更新本表 | `docs/ROADMAP.md` |

#### P2（架构/生产隐患）

| ID | 模块 | 任务 | 状态 | 说明 / 建议方案 | 相关文件 |
|----|------|------|------|-----------------|----------|
| R7 | 配置 | 修正 Dify 控制台地址端口 | 待修复 | `.env.example` 中 `CONSOLE_WEB_URL=http://localhost:3000` 与 FA 前端端口冲突，且与 README 不一致，应改为 `8080` | `.env.example` |
| R8 | 后端 | IMService 改为直接调用 service 层 | 待重构 | 当前用 `TestClient` 调内部 API，生产环境不推荐，应改为直接调用 `report_service` / `approval_service` / `query_service` | `backend/app/services/im_service.py` |

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
