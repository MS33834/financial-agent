"""初始化默认租户和管理员用户.

用法：
    python scripts/bootstrap.py

默认账号：admin / Admin123456
"""

import os
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
DEFAULT_ADMIN_PASSWORD = "Admin123456"


def bootstrap() -> None:
    """创建默认租户和管理员."""
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
            hashed_password=get_password_hash(DEFAULT_ADMIN_PASSWORD),
            role="admin",
            is_active="Y",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        print("Bootstrap success:")
        print(f"  Tenant: {tenant.name} ({tenant.id})")
        print(f"  User:   {user.username} ({user.id})")
        print(f"  Password: {DEFAULT_ADMIN_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    bootstrap()
