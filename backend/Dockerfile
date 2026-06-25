# 企业级财务智能体 - 后端服务 Dockerfile
FROM python:3.12-slim-bookworm AS builder

WORKDIR /app

# 安装构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e "."

# 运行阶段
FROM python:3.12-slim-bookworm

WORKDIR /app

# 安装运行时依赖（含中文 PDF 渲染字体）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    fonts-wqy-microhei \
    && rm -rf /var/lib/apt/lists/*

# 创建非 root 运行用户
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

# 复制虚拟环境（从 builder 复制 site-packages）
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制应用代码
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY scripts/ ./scripts/
COPY alembic.ini ./

# 确保启动脚本可执行并设置属主
RUN chmod +x ./scripts/entrypoint.sh && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

ENTRYPOINT ["./scripts/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--lifespan", "on", "--timeout-graceful-shutdown", "30"]
