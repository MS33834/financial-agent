"""ABAC 与字段加密测试."""

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.abac import ABACEngine
from app.core.encryption import EncryptedJSON, EncryptionError, FieldEncryption
from app.models.access_policy import AccessPolicy
from app.models.report import Report
from app.models.tenant import Tenant
from app.models.user import User
from app.security import get_password_hash


@pytest.fixture
def abac_tenant(db_session: Session) -> Tenant:
    """创建 ABAC 测试租户."""
    tenant = Tenant(name="ABAC Tenant", code="abac-test")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


@pytest.fixture
def abac_user(db_session: Session, abac_tenant: Tenant) -> User:
    """创建带有属性的测试用户."""
    user = User(
        tenant_id=abac_tenant.id,
        username="abac-user",
        email="abac@example.com",
        hashed_password=get_password_hash("testpass"),
        role="finance_manager",
        is_active="Y",
        attributes={"department": "finance", "level": 3},
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_abac_default_deny(
    db_session: Session,
    abac_user: User,
) -> None:
    """无策略时默认拒绝."""
    engine = ABACEngine(db_session)
    assert engine.evaluate(abac_user, "report", "read") is False


def test_abac_allow_policy(
    db_session: Session,
    abac_user: User,
    abac_tenant: Tenant,
) -> None:
    """匹配 allow 策略时允许."""
    policy = AccessPolicy(
        tenant_id=abac_tenant.id,
        name="finance can read report",
        resource_type="report",
        action="read",
        effect="allow",
        priority=100,
        conditions={"user.department": "finance"},
    )
    db_session.add(policy)
    db_session.commit()

    engine = ABACEngine(db_session)
    assert engine.evaluate(abac_user, "report", "read") is True


def test_abac_deny_priority(
    db_session: Session,
    abac_user: User,
    abac_tenant: Tenant,
) -> None:
    """deny 策略优先级高于 allow."""
    db_session.add_all(
        [
            AccessPolicy(
                tenant_id=abac_tenant.id,
                name="allow finance",
                resource_type="report",
                action="delete",
                effect="allow",
                priority=100,
                conditions={"user.department": "finance"},
            ),
            AccessPolicy(
                tenant_id=abac_tenant.id,
                name="deny low level delete",
                resource_type="report",
                action="delete",
                effect="deny",
                priority=10,
                conditions={"user.level": "lte:2"},
            ),
        ]
    )
    db_session.commit()

    engine = ABACEngine(db_session)
    # level=3 不匹配 deny，allow 生效
    assert engine.evaluate(abac_user, "report", "delete") is True

    # 修改用户 level 为 2，deny 生效
    abac_user.attributes = {"department": "finance", "level": 2}
    db_session.commit()
    assert engine.evaluate(abac_user, "report", "delete") is False


def test_abac_operators(
    db_session: Session,
    abac_user: User,
    abac_tenant: Tenant,
) -> None:
    """验证多种操作符."""
    policy = AccessPolicy(
        tenant_id=abac_tenant.id,
        name="complex conditions",
        resource_type="report",
        action="approve",
        effect="allow",
        priority=1,
        conditions={
            "user.level": "gte:3",
            "user.department": "in:finance,audit",
            "resource.sensitivity": "lte:2",
        },
    )
    db_session.add(policy)
    db_session.commit()

    engine = ABACEngine(db_session)
    assert engine.evaluate(
        abac_user,
        "report",
        "approve",
        resource_attributes={"sensitivity": 2},
    ) is True
    assert engine.evaluate(
        abac_user,
        "report",
        "approve",
        resource_attributes={"sensitivity": 3},
    ) is False


def test_field_encryption_roundtrip() -> None:
    """字段加密可正确加解密."""
    plaintext = {"revenue": 1_000_000, "net_profit": 150_000}
    ciphertext = FieldEncryption.encrypt(plaintext)
    assert ciphertext != str(plaintext)
    decrypted = FieldEncryption.decrypt(ciphertext)
    assert decrypted == plaintext


def test_field_encryption_string() -> None:
    """字符串加密可解密."""
    text = "敏感信息"
    ciphertext = FieldEncryption.encrypt(text)
    assert FieldEncryption.decrypt(ciphertext) == text


def test_field_encryption_none_raises() -> None:
    """加密 None 应抛出异常."""
    with pytest.raises(EncryptionError):
        FieldEncryption.encrypt(None)


def test_encrypted_json_type_decorator() -> None:
    """EncryptedJSON TypeDecorator 可正确加解密."""
    decorator = EncryptedJSON()
    value = {"key": "secret"}
    encrypted = decorator.process_bind_param(value, None)
    assert isinstance(encrypted, str)
    decrypted = decorator.process_result_value(encrypted, None)
    assert decrypted == value


def test_encrypted_string_type_decorator() -> None:
    """EncryptedString TypeDecorator 可正确加解密字符串."""
    from app.core.encryption import EncryptedString

    decorator = EncryptedString()
    value = "敏感摘要内容"
    encrypted = decorator.process_bind_param(value, None)
    assert isinstance(encrypted, str)
    assert encrypted != value
    decrypted = decorator.process_result_value(encrypted, None)
    assert decrypted == value


def test_encrypted_string_rejects_non_string() -> None:
    """EncryptedString 拒绝非字符串值."""
    from app.core.encryption import EncryptedString

    decorator = EncryptedString()
    with pytest.raises(EncryptionError):
        decorator.process_bind_param({"key": "value"}, None)


def test_report_summary_encrypted_at_rest(
    db_session: Session,
    test_user: User,
) -> None:
    """报告摘要落库应为加密形态，读取时自动解密."""
    report = Report(
        tenant_id=test_user.tenant_id,
        created_by=test_user.id,
        title="加密测试报告",
        report_type="profit",
        summary="高度敏感的利润摘要",
    )
    db_session.add(report)
    db_session.commit()

    # ORM 读取自动解密
    loaded = db_session.get(Report, report.id)
    assert loaded is not None
    assert loaded.summary == "高度敏感的利润摘要"

    # 直接查询数据库应得到密文
    raw = db_session.execute(
        sa.text("SELECT summary FROM reports WHERE id = :id"),
        {"id": report.id},
    ).scalar()
    assert raw is not None
    assert raw != "高度敏感的利润摘要"


def test_user_attributes_encrypted_at_rest(
    db_session: Session,
    test_tenant: Tenant,
) -> None:
    """用户 ABAC 属性落库应为加密形态，读取时自动解密."""
    user = User(
        tenant_id=test_tenant.id,
        username="encrypted_attrs_user",
        email="enc@example.com",
        hashed_password="hash",
        attributes={"department": "finance", "level": 3},
    )
    db_session.add(user)
    db_session.commit()

    loaded = db_session.get(User, user.id)
    assert loaded is not None
    assert loaded.attributes == {"department": "finance", "level": 3}

    raw = db_session.execute(
        sa.text("SELECT attributes FROM users WHERE id = :id"),
        {"id": user.id},
    ).scalar()
    assert raw is not None
    assert raw != '{"department": "finance", "level": 3}'
