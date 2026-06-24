"""对象存储客户端测试."""

# mypy: disable-error-code="attr-defined"

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from minio.error import S3Error

from app.storage import StorageClient, StorageClientError, get_storage_client


class TestStorageClient:
    """StorageClient 测试."""

    @pytest.fixture
    def storage(self) -> "Generator[StorageClient, None, None]":
        """创建带 mock MinIO 客户端的 StorageClient."""
        with patch("app.storage.get_settings") as mock_settings:
            settings = MagicMock()
            settings.minio_endpoint = "localhost:9000"
            settings.minio_access_key = "test"
            settings.minio_secret_key = "test"
            settings.minio_bucket = "financial-agent"
            settings.minio_public_url = "http://minio.example.com"
            mock_settings.return_value = settings

            client = StorageClient()
            client.client = MagicMock()
            yield client

    def test_ensure_bucket_creates_when_missing(self, storage: StorageClient) -> None:
        """bucket 不存在时应创建."""
        storage.client.bucket_exists.return_value = False
        storage.ensure_bucket()
        storage.client.bucket_exists.assert_called_once_with("financial-agent")
        storage.client.make_bucket.assert_called_once_with("financial-agent")

    def test_ensure_bucket_skips_when_exists(self, storage: StorageClient) -> None:
        """bucket 已存在时跳过创建."""
        storage.client.bucket_exists.return_value = True
        storage.ensure_bucket()
        storage.client.make_bucket.assert_not_called()

    def test_ensure_bucket_raises_on_s3_error(self, storage: StorageClient) -> None:
        """S3Error 应转换为 StorageClientError."""
        storage.client.bucket_exists.side_effect = S3Error(
            code="AccessDenied",
            message="access denied",
            resource="/bucket",
            request_id="req1",
            host_id="host1",
            response=MagicMock(),
        )
        with pytest.raises(StorageClientError):
            storage.ensure_bucket()

    def test_upload_bytes_success(self, storage: StorageClient) -> None:
        """上传字节数据成功并返回 public URL."""
        storage.client.bucket_exists.return_value = True
        url = storage.upload_bytes(
            key="reports/test.pdf",
            data=b"pdf-content",
            content_type="application/pdf",
            metadata={"tenant": "t1"},
        )

        assert url == "http://minio.example.com/financial-agent/reports/test.pdf"
        storage.client.put_object.assert_called_once()
        call_args = storage.client.put_object.call_args
        assert call_args.kwargs["content_type"] == "application/pdf"
        assert call_args.kwargs["metadata"] == {"tenant": "t1"}

    def test_upload_bytes_uses_endpoint_when_no_public_url(self, storage: StorageClient) -> None:
        """未配置 public_url 时使用 endpoint 构造 URL."""
        storage.public_url = ""
        storage.client._endpoint.url.netloc = "localhost:9000"
        storage.client.bucket_exists.return_value = True

        url = storage.upload_bytes(key="doc.txt", data=b"hello")
        assert url == "http://localhost:9000/financial-agent/doc.txt"

    def test_upload_bytes_raises_on_s3_error(self, storage: StorageClient) -> None:
        """上传失败时抛出 StorageClientError."""
        storage.client.bucket_exists.return_value = True
        storage.client.put_object.side_effect = S3Error(
            code="InternalError",
            message="internal error",
            resource="/object",
            request_id="req2",
            host_id="host2",
            response=MagicMock(),
        )
        with pytest.raises(StorageClientError):
            storage.upload_bytes(key="doc.txt", data=b"hello")

    def test_download_bytes_success(self, storage: StorageClient) -> None:
        """下载对象内容成功."""
        response = MagicMock()
        response.read.return_value = b"file-content"
        storage.client.get_object.return_value = response

        data = storage.download_bytes("doc.txt")
        assert data == b"file-content"
        storage.client.get_object.assert_called_once_with("financial-agent", "doc.txt")

    def test_download_bytes_raises_on_s3_error(self, storage: StorageClient) -> None:
        """下载失败时抛出 StorageClientError."""
        storage.client.get_object.side_effect = S3Error(
            code="NoSuchKey",
            message="not found",
            resource="/object",
            request_id="req3",
            host_id="host3",
            response=MagicMock(),
        )
        with pytest.raises(StorageClientError):
            storage.download_bytes("missing.txt")


class TestGetStorageClient:
    """get_storage_client 单例测试."""

    def test_returns_same_instance(self) -> None:
        """多次调用应返回同一实例."""
        with patch("app.storage.get_settings") as mock_settings:
            settings = MagicMock()
            settings.minio_endpoint = "localhost:9000"
            settings.minio_access_key = "test"
            settings.minio_secret_key = "test"
            settings.minio_bucket = "financial-agent"
            settings.minio_public_url = ""
            mock_settings.return_value = settings

            client1 = get_storage_client()
            client2 = get_storage_client()
            assert client1 is client2

        get_storage_client.cache_clear()
