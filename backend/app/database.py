"""数据库连接与会话管理.

MVP 阶段使用同步 SQLAlchemy + PostgreSQL，后续可按需迁移到异步。
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 声明式基类."""

    pass


# 创建引擎
engine = create_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# 会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI Dependency：获取数据库会话."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
