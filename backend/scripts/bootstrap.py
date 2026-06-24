"""初始化默认租户和管理员用户.

用法：
    python scripts/bootstrap.py

默认账号：admin，密码从环境变量 INIT_PASSWORD 读取；
未设置时自动生成随机强密码并打印到控制台。
"""

import os
import secrets
import string
import sys

# 将 backend 目录加入路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.tenant import Tenant
from app.models.user import User
from app.security import get_password_hash

DEFAULT_TENANT_NAME = "Default Tenant"
DEFAULT_TENANT_CODE = "default"
DEFAULT_ADMIN_USERNAME = "admin"


def _resolve_admin_password() -> str:
    """从环境变量读取管理员密码，未设置时生成随机强密码."""
    password = os.environ.get("INIT_PASSWORD", "").strip()
    if password:
        return password
    # 生成 16 位随机密码：字母 + 数字，避免歧义字符
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(16))


def bootstrap() -> None:
    """创建默认租户和管理员."""
    admin_password = _resolve_admin_password()
    db = SessionLocal()
    try:
        existing_tenant = db.query(Tenant).filter(Tenant.code == DEFAULT_TENANT_CODE).first()
        if existing_tenant:
            print(f"Tenant '{DEFAULT_TENANT_CODE}' already exists. Skipping.")
            return

        tenant = Tenant(name=DEFAULT_TENANT_NAME, code=DEFAULT_TENANT_CODE)
        db.add(tenant)
        db.commit()
        db.refresh(tenant)

        existing_user = db.query(User).filter(User.username == DEFAULT_ADMIN_USERNAME).first()
        if existing_user:
            print(f"User '{DEFAULT_ADMIN_USERNAME}' already exists. Skipping.")
            return

        user = User(
            tenant_id=tenant.id,
            username=DEFAULT_ADMIN_USERNAME,
            email="admin@example.com",
            hashed_password=get_password_hash(admin_password),
            role="admin",
            is_active="Y",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        print("Bootstrap success:")
        print(f"  Tenant: {tenant.name} ({tenant.id})")
        print(f"  User:   {user.username} ({user.id})")
        print(f"  Password: {admin_password}")
        if not os.environ.get("INIT_PASSWORD", "").strip():
            print("  WARNING: INIT_PASSWORD 未设置，已生成随机密码，请妥善保存。")
            print("  生产环境请通过 INIT_PASSWORD 环境变量显式指定。")
    finally:
        db.close()


if __name__ == "__main__":
    bootstrap()
