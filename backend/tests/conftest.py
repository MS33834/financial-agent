"""Pytest 共享 Fixture."""

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# 强制使用测试环境
os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-32-char-long-xxx")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")
os.environ.setdefault("MINIO_ENDPOINT", "localhost:9000")
os.environ.setdefault("MINIO_ACCESS_KEY", "test")
os.environ.setdefault("MINIO_SECRET_KEY", "test")
os.environ.setdefault("FEISHU_ENCRYPT_KEY", "test-encrypt-key-32-char-long-xx")
os.environ.setdefault("WECOM_TOKEN", "test-wecom-token")
os.environ.setdefault("WECOM_ENCODING_AES_KEY", "GrmBxZ5RRwnsMVH3deD/+WL+VaSHWmDTVJLMuYid18M")

from app.database import Base, get_db
from app.main import app
from app.models.tenant import Tenant
from app.models.user import User
from app.security import create_access_token, get_password_hash

# 内存/文件 SQLite 引擎
engine = create_engine(
    os.environ["DATABASE_URL"],
    connect_args={"check_same_thread": False} if "sqlite" in os.environ["DATABASE_URL"] else {},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_database() -> Generator[None, None, None]:
    """测试会话开始时建表，结束时删表."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """每个测试用例独立数据库会话."""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """FastAPI 测试客户端，使用测试数据库会话."""

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_tenant(db_session: Session) -> Tenant:
    """创建测试租户."""
    tenant = Tenant(name="Test Tenant", code="test")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


@pytest.fixture
def test_user(db_session: Session, test_tenant: Tenant) -> User:
    """创建测试用户."""
    user = User(
        tenant_id=test_tenant.id,
        username="testuser",
        email="test@example.com",
        hashed_password=get_password_hash("testpass"),
        role="admin",
        is_active="Y",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user: User) -> dict[str, str]:
    """生成测试用户的认证头."""
    token = create_access_token({"sub": test_user.id})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def viewer_user(db_session: Session, test_tenant: Tenant) -> User:
    """创建只读角色的测试用户."""
    user = User(
        tenant_id=test_tenant.id,
        username="viewer",
        email="viewer@example.com",
        hashed_password=get_password_hash("testpass"),
        role="viewer",
        is_active="Y",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def viewer_auth_headers(viewer_user: User) -> dict[str, str]:
    """生成只读用户的认证头."""
    token = create_access_token({"sub": viewer_user.id})
    return {"Authorization": f"Bearer {token}"}
