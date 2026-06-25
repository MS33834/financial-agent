"""对象存储客户端.

默认使用本地文件系统存储（LocalStorageClient），无需任何外部依赖。
配置 storage_backend=minio 时切换到 MinIO 对象存储（适合分布式部署）。
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.logger import get_logger

logger = get_logger(__name__)


class StorageClientError(Exception):
    """对象存储操作异常."""

    pass


class BaseStorageClient(ABC):
    """存储客户端抽象基类."""

    @abstractmethod
    def upload_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """上传字节数据并返回访问 URL."""
        raise NotImplementedError

    @abstractmethod
    def download_bytes(self, key: str) -> bytes:
        """下载对象内容."""
        raise NotImplementedError


class LocalStorageClient(BaseStorageClient):
    """基于本地文件系统的存储客户端.

    默认后端，无需任何外部依赖。
    文件存储在配置的 ``storage_local_root`` 目录下。
    """

    def __init__(self) -> None:
        """初始化本地存储客户端."""
        settings = get_settings()
        self.root = Path(settings.storage_local_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        logger.info("storage.local.ready", root=str(self.root))

    def upload_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """上传字节数据到本地文件系统.

        Args:
            key: 对象 key，作为相对路径。
            data: 文件内容。
            content_type: MIME 类型（本地存储忽略，仅记录日志）。
            metadata: 自定义元数据（本地存储忽略）。

        Returns:
            文件本地路径。
        """
        # 防止路径穿越：key 不允许包含 ..
        if ".." in key.split("/"):
            raise StorageClientError("对象 key 不允许包含 '..'")

        file_path = self.root / key
        file_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            file_path.write_bytes(data)
        except OSError as exc:
            raise StorageClientError(f"本地存储写入失败: {exc}") from exc
        return str(file_path)

    def download_bytes(self, key: str) -> bytes:
        """从本地文件系统读取对象内容.

        Args:
            key: 对象 key。

        Returns:
            文件原始字节。

        Raises:
            StorageClientError: 文件不存在或读取失败。
        """
        if ".." in key.split("/"):
            raise StorageClientError("对象 key 不允许包含 '..'")

        file_path = self.root / key
        if not file_path.exists():
            raise StorageClientError(f"对象不存在: {key}")
        try:
            return file_path.read_bytes()
        except OSError as exc:
            raise StorageClientError(f"本地存储读取失败: {exc}") from exc


class MinioStorageClient(BaseStorageClient):
    """基于 MinIO 的对象存储客户端.

    可选后端，适合分布式部署场景。需配置 MinIO 服务端点。
    """

    def __init__(self) -> None:
        """从配置初始化 MinIO 客户端."""
        from minio import Minio  # 延迟导入，仅使用 MinIO 时才需要

        settings = get_settings()
        if not settings.minio_endpoint:
            raise StorageClientError("MinIO 后端未配置 minio_endpoint")

        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=False,
        )
        self.bucket = settings.minio_bucket
        self.public_url = settings.minio_public_url

    def ensure_bucket(self) -> None:
        """确保 Bucket 存在."""
        from minio.error import S3Error

        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                logger.info("minio.bucket.created", bucket=self.bucket)
        except S3Error as exc:
            raise StorageClientError(f"无法创建 MinIO bucket: {exc}") from exc

    def upload_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """上传字节数据到 MinIO 并返回访问 URL."""
        from minio.error import S3Error

        self.ensure_bucket()
        stream = BytesIO(data)
        try:
            self.client.put_object(
                self.bucket,
                key,
                stream,
                length=len(data),
                content_type=content_type,
                metadata=metadata or {},
            )
        except S3Error as exc:
            raise StorageClientError(f"上传失败: {exc}") from exc

        base = self.public_url or f"http://{self.client._endpoint.url.netloc}"  # type: ignore[attr-defined]
        return f"{base}/{self.bucket}/{key}"

    def download_bytes(self, key: str) -> bytes:
        """从 MinIO 下载对象内容."""
        from minio.error import S3Error

        try:
            response = self.client.get_object(self.bucket, key)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()
        except S3Error as exc:
            raise StorageClientError(f"下载失败: {exc}") from exc


@lru_cache
def get_storage_client() -> BaseStorageClient:
    """获取存储客户端单例.

    根据 ``storage_backend`` 配置返回对应实现：
    - ``local``（默认）：LocalStorageClient，本地文件系统，无外部依赖
    - ``minio``：MinioStorageClient，MinIO 对象存储，适合分布式部署
    """
    settings = get_settings()
    backend = settings.storage_backend.lower()

    if backend == "minio":
        logger.info("storage.backend=minio")
        return MinioStorageClient()

    logger.info("storage.backend=local")
    return LocalStorageClient()
