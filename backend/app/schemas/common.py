"""通用 Schema."""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class BaseResponse(BaseModel):
    """统一响应基类."""

    code: int = Field(default=0, description="业务状态码")
    message: str = Field(default="ok", description="提示信息")
    request_id: str | None = Field(default=None, description="请求 ID")


class DataResponse(BaseResponse, Generic[T]):
    """带数据的统一响应."""

    data: T = Field(description="业务数据")


class PaginationParams(BaseModel):
    """分页参数."""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")


class PaginatedData(BaseModel, Generic[T]):
    """分页数据."""

    total: int = Field(description="总数")
    page: int = Field(description="当前页")
    page_size: int = Field(description="每页数量")
    items: list[T] = Field(description="数据列表")


class PaginatedResponse(BaseResponse, Generic[T]):
    """分页响应."""

    data: PaginatedData[T] = Field(description="分页数据")
