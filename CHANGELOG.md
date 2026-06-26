# 更新日志

本项目所有重要变更均记录于此文件。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
并遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

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
