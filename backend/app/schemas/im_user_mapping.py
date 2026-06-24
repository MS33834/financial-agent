"""IM 用户映射相关 Schema."""

from typing import Literal

from pydantic import BaseModel, Field

# 支持的 IM 平台白名单
IMPlatform = Literal["dingtalk", "feishu", "wecom"]


class IMUserMappingCreate(BaseModel):
    """创建 IM 用户映射请求."""

    user_id: str = Field(description="系统用户 ID", min_length=1)
    platform: IMPlatform = Field(description="IM 平台: dingtalk/feishu/wecom")
    im_user_id: str = Field(description="IM 平台用户唯一标识", min_length=1, max_length=128)


class IMUserMappingResponse(BaseModel):
    """IM 用户映射响应."""

    id: str = Field(description="映射 ID")
    user_id: str = Field(description="系统用户 ID")
    platform: str = Field(description="IM 平台")
    im_user_id: str = Field(description="IM 平台用户唯一标识")
    created_at: str | None = Field(default=None, description="创建时间")
    updated_at: str | None = Field(default=None, description="更新时间")


def serialize_im_user_mapping(mapping) -> dict:  # type: ignore[no-untyped-def]
    """将 IMUserMapping ORM 对象序列化为响应字典."""
    return {
        "id": mapping.id,
        "user_id": mapping.user_id,
        "platform": mapping.platform,
        "im_user_id": mapping.im_user_id,
        "created_at": mapping.created_at.isoformat() if mapping.created_at else None,
        "updated_at": mapping.updated_at.isoformat() if mapping.updated_at else None,
    }

