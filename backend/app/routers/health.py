"""健康检查路由."""

from fastapi import APIRouter, status

from app.schemas.common import BaseResponse

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", status_code=status.HTTP_200_OK, response_model=BaseResponse)
def health_check() -> BaseResponse:
    """服务健康检查."""
    return BaseResponse(code=0, message="ok")


@router.get("/ready", status_code=status.HTTP_200_OK, response_model=BaseResponse)
def readiness_check() -> BaseResponse:
    """就绪检查（后续可检查 DB、Redis 连通性）."""
    return BaseResponse(code=0, message="ready")
