"""对象存储客户端（MinIO）."""

from functools import lru_cache
from io import BytesIO
from typing import Any

from minio import Minio
from minio.error import S3Error

from app.config import get_settings
from app.logger import get_logger

logger = get_logger(__name__)


class StorageClientError(Exception):
    """对象存储操作异常."""

    pass


class StorageClient:
    """基于 MinIO 的对象存储客户端封装."""

    def __init__(self) -> None:
        """从配置初始化客户端."""
        settings = get_settings()
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
        """上传字节数据并返回访问 URL.

        Args:
            key: 对象 key。
            data: 文件内容。
            content_type: MIME 类型。
            metadata: 自定义元数据。

        Returns:
            对象访问 URL（优先使用 public_url）。
        """
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
        """下载对象内容.

        Args:
            key: 对象 key。

        Returns:
            对象原始字节。

        Raises:
            StorageClientError: 下载失败时抛出。
        """
        try:
            response = self.client.get_object(self.bucket, key)
            return response.read()
        except S3Error as exc:
            raise StorageClientError(f"下载失败: {exc}") from exc


@lru_cache
def get_storage_client() -> StorageClient:
    """获取存储客户端单例."""
    return StorageClient()
