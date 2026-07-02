# 更新日志

本项目所有重要变更均记录于此文件。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
并遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [0.2.1] - 2026-07-02

验收阶段：CI 修复、e2e 测试补全、安全扫描、性能基准、部署文档完善。

### 修复

- 修复 `notifications.py` 从 `app.dependencies` 误导入 `get_current_user`（应从 `app.security` 导入）
- 修复 `test_storage_more.py` 中 `_patch[MagicMock]` 泛型下标导致 CI 收集阶段 `TypeError`（CI 连续 8 次失败的根因）
- 统一 `pyproject.toml` 中 ruff/mypy 目标版本为 `py312`（与 `requires-python>=3.12` 一致）
- 测试文件补全 84 处 mypy 类型注解，清理 48 处 ruff 问题（未使用导入/变量、嵌套 with、死代码）
- 修复 `IntegrityError`/`S3Error` 构造参数类型不匹配

### 新增

- 4 个 e2e 测试：上传文档、生成报告、审批操作、Agent 对话（覆盖完整用户旅程）
- `CONTRIBUTING.md` 新增「开发者必做检查清单」（CI/PR/Issue/分支/同步/安全 6 项）
- `docs/ops/deployment.md` 新增「生产环境检查清单」「回滚流程」「HTTPS/TLS 配置」章节
- `docs/ops/monitoring.md` 新增「日志收集」「Alertmanager 路由建议」章节，修正健康端点路径
- `.env.example` 补齐 15+ 缺失配置项（OpenAI/SMTP/JWT/分页等）
- `values.yaml` 补齐 `CORS_ORIGINS`、IM 密钥、`persistence` 等关键配置

### 增强

- `benchmark.py` 支持本地模式（`BENCH_READY_STATUS` 环境变量适配可选依赖）
- `docs/user-guide.md` 修正报告状态列表和演示账号说明
- `docs/admin-guide.md` 补充 `auditor` 角色和 ABAC 策略说明

### 验证结果

- 后端：504 passed / 22 skipped，覆盖率 90.34%，ruff + mypy 0 errors
- 前端：106 passed，lint/build 通过，覆盖率 90.51%
- CI：8 个 job 全部 success
- 安全：npm audit 0 vulns，pip-audit 项目依赖无 HIGH/CRITICAL 漏洞
- 性能：50 并发请求，所有端点 P95 < 0.04s（目标 < 2s）
- e2e：8 个测试覆盖 5 个核心用户旅程

## [0.2.0] - 2026-06-26

功能增强批次。

### 新增

- 通知服务模块（邮件/IM/站内信多渠道）
- API Key 生命周期管理（使用统计、密钥轮换）
- 独立 Worker 模块（优雅关闭、任务监控）
- shared 共享契约模块（常量、事件、schemas）
- Agent 多轮对话与错误恢复
- RAG 持久化索引（PostgreSQL 回退查询）
- 报告模板化与自定义模板注册
- 字段级加密密钥轮换
- Redis 分布式限流
- OpenTelemetry 链路追踪
- 用户管理/API Key 管理/IM 映射/系统设置 4 个前端页面
- 404 页面
- 用户 CRUD API
- 通知管理 API
- API Key 轮换 API
- API 层集成测试

### 增强

- 增强 IM 命令错误边界测试
- 提升核心模块测试覆盖率

### 已知问题

- 前端依赖审计（`npm audit`）未发现 HIGH/CRITICAL 漏洞（共 409 个依赖，0 个漏洞）。
- 后端 `pip-audit` 未安装，本次未执行后端依赖漏洞扫描；建议在 CI 中引入 `pip-audit` 步骤以补齐后端供应链安全检查。
- Python 版本基线统一为 3.12（CI matrix、Dockerfile、`requires-python` 三处一致），部分本地开发环境仍可能使用更高版本（如 3.14），请确保工具链（ruff/mypy）配置与之兼容。

## [0.1.0] - 2026-06-25

MVP 初始版本。

### 新增

- 财务报告生成、文档解析、智能问答、审批流程
- 多租户、ABAC、审计日志
- Dify 集成、Ollama 本地 LLM
- Docker Compose / Helm 部署
