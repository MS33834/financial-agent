# ==================================================================
# 企业级财务智能体 - MVP 本地开发命令
# ==================================================================

# 加载 .env 中的变量，供 Makefile 目标使用
-include .env
export

PROJECT_NAME := financial-agent
COMPOSE_FILE := docker-compose.yml
COMPOSE_PROD_FILE := docker-compose.prod.yml

.PHONY: help init validate validate-prod up up-build up-prod down down-volumes logs logs-api logs-backend logs-frontend pull-model create-bucket shell-ollama shell-api shell-backend status test lint backend-test backend-lint backend-migrate backend-seed-demo

help: ## 显示可用命令
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

init: ## 初始化项目：克隆 Dify vendor、创建 .env
	@if [ ! -d "vendor/dify" ]; then \
		echo "==> Cloning Dify vendor..."; \
		git clone --depth 1 https://github.com/langgenius/dify.git vendor/dify; \
	else \
		echo "==> Dify vendor already exists."; \
	fi
	@if [ ! -f ".env" ]; then \
		echo "==> Creating .env from .env.example..."; \
		cp .env.example .env; \
		echo "Please review and update .env if needed."; \
	else \
		echo "==> .env already exists."; \
	fi
	@echo "==> Syncing .env to vendor/dify/docker/.env for Dify include..."
	@cp .env vendor/dify/docker/.env

validate: ## 校验 docker-compose.yml 配置（无需启动 Docker）
	@echo "==> Validating Docker Compose configuration..."
	@cp -f .env vendor/dify/docker/.env
	@docker compose -f $(COMPOSE_FILE) config > /dev/null && echo "Compose configuration is valid."

validate-prod: ## 校验生产环境 Compose 配置（无需启动 Docker）
	@echo "==> Validating production Docker Compose configuration..."
	@docker compose -f $(COMPOSE_FILE) -f $(COMPOSE_PROD_FILE) config > /dev/null && echo "Production compose configuration is valid."

up: ## 启动全部服务（后台）
	docker compose -f $(COMPOSE_FILE) --env-file .env up -d

up-build: ## 启动全部服务并重新构建
	docker compose -f $(COMPOSE_FILE) --env-file .env up -d --build

up-prod: ## 以生产模式启动全部服务（后台）
	docker compose -f $(COMPOSE_FILE) -f $(COMPOSE_PROD_FILE) --env-file .env up -d

down: ## 停止并移除全部服务
	docker compose -f $(COMPOSE_FILE) down

down-volumes: ## 停止服务并删除数据卷（危险：数据清空）
	docker compose -f $(COMPOSE_FILE) down -v

logs: ## 查看所有服务日志（跟随模式）
	docker compose -f $(COMPOSE_FILE) logs -f

logs-api: ## 查看 Dify API 日志
	docker compose -f $(COMPOSE_FILE) logs -f api

logs-backend: ## 查看后端服务日志
	docker compose -f $(COMPOSE_FILE) logs -f backend

logs-frontend: ## 查看前端服务日志
	docker compose -f $(COMPOSE_FILE) logs -f frontend

pull-model: ## 拉取 Ollama 模型（默认 qwen2.5:7b，可在 .env 中修改）
	@if [ -z "$(OLLAMA_MODEL)" ]; then \
		echo "OLLAMA_MODEL is not set. Please check your .env file."; \
		exit 1; \
	fi
	docker compose -f $(COMPOSE_FILE) exec fa-ollama ollama pull $(OLLAMA_MODEL)

create-bucket: ## 在 MinIO 中创建 financial-agent bucket
	@docker compose -f $(COMPOSE_FILE) exec fa-minio sh -c \
	"mc alias set local http://localhost:9000 $(MINIO_ROOT_USER) $(MINIO_ROOT_PASSWORD) >/dev/null 2>&1 || true; \
	 mc mb local/$(MINIO_BUCKET:-financial-agent) >/dev/null 2>&1 || true; \
	 mc anonymous set download local/$(MINIO_BUCKET:-financial-agent) >/dev/null 2>&1 || true; \
	 echo 'Bucket $(MINIO_BUCKET:-financial-agent) ready.'"

shell-ollama: ## 进入 Ollama 容器
	docker compose -f $(COMPOSE_FILE) exec fa-ollama /bin/sh

shell-api: ## 进入 Dify API 容器
	docker compose -f $(COMPOSE_FILE) exec api /bin/sh

shell-backend: ## 进入后端服务容器
	docker compose -f $(COMPOSE_FILE) exec backend /bin/sh

status: ## 查看所有服务运行状态
	docker compose -f $(COMPOSE_FILE) ps

test: backend-test ## 运行全部测试（默认后端测试）

lint: backend-lint ## 运行全部代码检查（默认后端检查）

backend-test: ## 运行后端测试（使用 SQLite 内存测试库）
	cd backend && APP_ENV=testing DATABASE_URL="sqlite:///./test.db" python -m pytest

backend-lint: ## 运行后端代码检查（ruff + mypy）
	cd backend && python -m ruff check app tests
	cd backend && python -m mypy app tests

backend-worker: ## 启动后端 Celery Worker
	cd backend && python scripts/worker.py

backend-migrate: ## 运行后端数据库迁移
	cd backend && alembic upgrade head

backend-migration: ## 自动生成数据库迁移脚本（需先确认模型变更）
	cd backend && alembic revision --autogenerate -m "$(message)"

backend-seed-demo: ## 初始化 MVP 演示财务数据（3 个月 Q1/Q2/Q3）
	cd backend && python scripts/seed_demo_data.py

backend-train-vanna: ## 训练 Vanna Text2SQL 模型
	cd backend && DATABASE_URL=$(DATABASE_URL) OLLAMA_MODEL=$(OLLAMA_MODEL) OLLAMA_HOST=$(OLLAMA_HOST) python scripts/train_vanna.py
