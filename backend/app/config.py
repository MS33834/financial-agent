"""应用配置管理.

所有配置均从环境变量读取，遵循 12-Factor App 原则。
敏感信息不硬编码，通过 .env 或运行时注入。
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 应用基础
    app_name: str = Field(default="financial-agent-backend", description="应用名称")
    app_env: str = Field(default="development", description="运行环境")
    debug: bool = Field(default=False, description="调试模式")
    log_level: str = Field(default="INFO", description="日志级别")

    # 安全
    secret_key: str = Field(description="JWT / 加密密钥")
    access_token_expire_minutes: int = Field(
        default=60 * 24, description="Access Token 有效期（分钟）"
    )
    algorithm: str = Field(default="HS256", description="JWT 算法")

    # 数据库
    # 使用 str 而非 PostgresDsn，允许测试时使用 SQLite
    database_url: str = Field(description="数据库连接 URL")
    database_echo: bool = Field(default=False, description="是否打印 SQL")

    # 缓存 / 队列
    redis_url: str = Field(description="Redis 连接 URL")
    celery_broker_url: str | None = Field(default=None, description="Celery Broker URL")
    celery_result_backend: str | None = Field(default=None, description="Celery Result Backend")

    # 对象存储
    minio_endpoint: str = Field(description="MinIO 服务端点")
    minio_access_key: str = Field(description="MinIO Access Key")
    minio_secret_key: str = Field(description="MinIO Secret Key")
    minio_bucket: str = Field(default="financial-agent", description="MinIO Bucket")
    minio_public_url: str | None = Field(default=None, description="MinIO 公网访问地址")

    # Ollama
    ollama_host: str = Field(default="http://fa-ollama:11434", description="Ollama 服务地址")
    ollama_model: str = Field(default="qwen2.5:7b", description="默认 Ollama 模型")

    # Dify 流程编排
    dify_base_url: str | None = Field(
        default=None, description="Dify API 基础地址，如 http://localhost:5001/v1"
    )
    dify_api_key: str | None = Field(default=None, description="Dify Workflow/API 密钥")
    dify_workflow_id: str | None = Field(default=None, description="默认 Dify Workflow ID")
    dify_tool_api_key: str | None = Field(
        default=None, description="Dify 调用后端 Tools 时使用的 API Key"
    )

    # Text2SQL
    text2sql_backend: str = Field(
        default="rule", description="Text2SQL 后端: rule/vanna"
    )

    # Agent LLM 意图识别与 RAG
    agent_intent_mode: str = Field(
        default="llm", description="Agent 意图识别模式: llm/rule"
    )
    agent_llm_model: str = Field(
        default="qwen2.5:7b", description="Agent LLM 模型名"
    )
    rag_chunk_size: int = Field(default=512, description="RAG 文本切分大小")
    rag_top_k: int = Field(default=3, description="RAG 返回 chunk 数量")

    # IM 机器人
    dingtalk_app_secret: str | None = Field(
        default=None, description="钉钉机器人加签密钥"
    )
    dingtalk_webhook: str | None = Field(
        default=None, description="钉钉机器人 Webhook 地址，用于主动推送消息"
    )
    feishu_encrypt_key: str | None = Field(
        default=None, description="飞书事件订阅 Encrypt Key"
    )
    feishu_webhook: str | None = Field(
        default=None, description="飞书机器人 Webhook 地址，用于主动推送消息"
    )
    wecom_token: str | None = Field(
        default=None, description="企业微信回调 Token"
    )
    wecom_encoding_aes_key: str | None = Field(
        default=None, description="企业微信回调 EncodingAESKey"
    )
    wecom_webhook: str | None = Field(
        default=None, description="企业微信机器人 Webhook 地址，用于主动推送消息"
    )
    # Mineru / Magic-PDF 解析服务
    mineru_api_url: str | None = Field(
        default=None, description="Mineru 解析服务 HTTP API 地址"
    )
    mineru_timeout: int = Field(default=120, description="Mineru 请求超时（秒）")

    # 业务
    default_page_size: int = Field(default=20, description="默认分页大小")
    max_page_size: int = Field(default=100, description="最大分页大小")

    # 生产加固
    cors_origins: list[str] = Field(
        default=["*"], description="CORS 允许的源列表，生产环境应限制为前端域名"
    )
    rate_limit_enabled: bool = Field(
        default=True, description="是否启用请求速率限制"
    )
    rate_limit_max_requests: int = Field(
        default=120, description="速率限制窗口内最大请求数"
    )
    rate_limit_window_seconds: int = Field(
        default=60, description="速率限制时间窗口（秒）"
    )


@lru_cache
def get_settings() -> Settings:
    """获取配置单例.

    实际字段值从环境变量/ .env 文件读取，类型检查器无法推断，故忽略构造参数检查。
    """
    return Settings()  # type: ignore[call-arg]
