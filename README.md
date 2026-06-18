# 企业级财务智能体（MVP）

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

> 一个基于 Dify + LangGraph + Ollama + Mineru + Vanna 的企业级财务智能体 MVP。

---

## 1. 项目简介

本项目目标是在 4 周内完成财务智能体的最小可用原型（MVP），实现：

- 用户通过 Web 上传 PDF/Excel 财务文件。
- 系统自动解析并提取结构化数据。
- 用户通过自然语言查询财务数据。
- 系统生成利润表、资产负债表等基础报告。
- 关键报告触发人工审核流程。
- 所有操作记录审计日志。
- 支持本地轻薄本部署（Ollama + Qwen2.5）。

详细规划见：

- [`enterprise_financial_ai_agent_plan_v3.1.md`](../enterprise_financial_ai_agent_plan_v3.1.md)
- [`mvp_execution_plan.md`](../mvp_execution_plan.md)

---

## 2. 环境要求

### 2.1 硬件

| 场景 | CPU | 内存 | 磁盘 | 备注 |
|------|-----|------|------|------|
| 开发机 | ≥4 核 | ≥16GB | ≥50GB SSD | 推荐 |
| 轻薄本 | ≥4 核 | ≥16GB | ≥50GB SSD | 使用 `qwen2.5:3b` 模型 |

### 2.2 软件

- Docker Engine ≥ 24.0
- Docker Compose ≥ 2.20（支持 `include` 语法）
- Git
- Make（可选，推荐）

---

## 3. 快速开始

### 3.1 克隆与初始化

```bash
cd /workspace/financial-agent
make init
```

`make init` 会：

1. 克隆 Dify 官方仓库到 `vendor/dify`。
2. 从 `.env.example` 生成 `.env`。

### 3.2 启动服务

```bash
make up
```

首次启动会拉取镜像并初始化 Dify 数据库，可能需要 5-10 分钟。

### 3.3 检查服务状态

```bash
make status
```

关键服务：

| 服务 | 地址 | 说明 |
|------|------|------|
| Dify 控制台 | http://localhost:3000 | 默认账号 `admin@dify.ai` / `.env` 中 `INIT_PASSWORD` |
| Dify API | http://localhost:5001 | 后端 API |
| Dify Nginx | http://localhost:8080 | 统一入口（API + Web） |
| Ollama | http://localhost:11434 | 本地大模型服务 |
| MinIO 控制台 | http://localhost:9001 | 对象存储管理 |
| MinIO API | http://localhost:9000 | S3 兼容 API |

### 3.4 拉取大模型

```bash
make pull-model
```

默认拉取 `qwen2.5:7b`。若硬件资源紧张，修改 `.env` 中的 `OLLAMA_MODEL` 为 `qwen2.5:3b` 后重新执行。

### 3.5 初始化 MinIO Bucket

```bash
make create-bucket
```

### 3.6 停止服务

```bash
make down
```

---

## 4. 目录结构

```
financial-agent/
├── .github/
│   └── pull_request_template.md   # PR 模板
├── backend/
│   ├── agent_runtime/             # LangGraph Agent 运行时
│   ├── audit_service/             # 审计日志服务
│   ├── notification/              # 通知服务
│   ├── report_service/            # 报表生成服务
│   └── vanna_engine/              # Text2SQL 引擎
├── docs/
│   ├── api/                       # API 文档
│   ├── design/                    # 设计文档
│   └── ops/                       # 运维文档
├── frontend/                      # React Web 前端
├── shared/                        # 公共模型与工具
├── tests/                         # 测试用例
├── vendor/
│   └── dify/                      # Dify 官方代码（git clone）
├── workers/                       # PDF 解析 Worker（Mineru）
├── docker-compose.yml             # 容器编排
├── .env.example                   # 环境变量示例
├── .gitignore
├── Makefile                       # 常用命令
└── README.md                      # 本文件
```

---

## 5. 开发流程

### 5.1 分支策略（Trunk-Based）

- `main`：主分支，始终保持可部署。
- 功能分支：`feature/<简短描述>`，例如 `feature/text2sql-validation`。
- 修复分支：`fix/<简短描述>`。
- 每个 PR 需至少 1 人 Review 并通过 CI 检查。

### 5.2 提交规范

```
<type>(<scope>): <subject>

<body>

<footer>
```

常用 type：

- `feat`：新功能
- `fix`：Bug 修复
- `docs`：文档
- `style`：格式调整
- `refactor`：重构
- `test`：测试
- `chore`：构建/工具

示例：

```
feat(text2sql): 添加 SQL 白名单校验

- 禁止 DROP/DELETE/UPDATE 等 DML/DDL 关键字
- 自动注入 tenant_id 过滤条件
```

### 5.3 PR 模板

见 [`.github/pull_request_template.md`](.github/pull_request_template.md)。

---

## 6. 常见问题

### Q1: `make init` 克隆 Dify 失败？

检查网络连接，或手动执行：

```bash
git clone --depth 1 https://github.com/langgenius/dify.git vendor/dify
```

### Q2: Dify 启动后 8080 端口无法访问？

检查 `.env` 中 `EXPOSE_NGINX_PORT` 是否与其他服务冲突。可改为 `8081` 后重新 `make up`。

### Q3: Ollama 模型下载慢？

可使用国内镜像或手动下载后挂载到 `ollama_data` 卷。

### Q4: 如何进入容器调试？

```bash
make shell-api      # Dify API
make shell-ollama   # Ollama
```

---

## 7. 下一步

1. **Week 1 Day 1-2**：完成环境初始化（当前已完成基础设施）。
2. **Week 1 Day 3-4**：在 Dify 中配置 Ollama 模型，验证基础对话。
3. **Week 1 Day 5**：搭建后端 FastAPI 骨架。

详细任务拆分见 [`mvp_execution_plan.md`](../mvp_execution_plan.md)。

---

## 8. 许可证

MIT
