"""对象存储客户端测试.

覆盖默认的 LocalStorageClient（本地文件系统）与可选的 MinioStorageClient。
"""

# mypy: disable-error-code="attr-defined"

from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.storage import (
    BaseStorageClient,
    LocalStorageClient,
    MinioStorageClient,
    StorageClientError,
    get_storage_client,
)


class TestLocalStorageClient:
    """LocalStorageClient（默认本地后端）测试."""

    @pytest.fixture
    def storage(self, tmp_path: Path) -> Generator[LocalStorageClient, None, None]:
        """创建指向临时目录的 LocalStorageClient."""
        with patch("app.storage.get_settings") as mock_settings:
            settings = MagicMock()
            settings.storage_local_root = str(tmp_path)
            mock_settings.return_value = settings
            client = LocalStorageClient()
            yield client

    def test_upload_bytes_writes_file(self, storage: LocalStorageClient, tmp_path: Path) -> None:
        """上传字节数据应写入文件并返回路径."""
        url = storage.upload_bytes(
            key="reports/test.pdf",
            data=b"pdf-content",
            content_type="application/pdf",
            metadata={"tenant": "t1"},
        )
        assert "reports/test.pdf" in url
        assert (tmp_path / "reports" / "test.pdf").read_bytes() == b"pdf-content"

    def test_upload_bytes_creates_nested_dirs(
        self, storage: LocalStorageClient, tmp_path: Path
    ) -> None:
        """上传到深层路径应自动创建父目录."""
        storage.upload_bytes(key="a/b/c/d.txt", data=b"deep")
        assert (tmp_path / "a" / "b" / "c" / "d.txt").read_bytes() == b"deep"

    def test_download_bytes_returns_content(
        self, storage: LocalStorageClient
    ) -> None:
        """下载应返回写入的文件内容."""
        storage.upload_bytes(key="doc.txt", data=b"hello")
        assert storage.download_bytes("doc.txt") == b"hello"

    def test_download_bytes_raises_when_missing(
        self, storage: LocalStorageClient
    ) -> None:
        """文件不存在时应抛出 StorageClientError."""
        with pytest.raises(StorageClientError):
            storage.download_bytes("missing.txt")

    def test_upload_rejects_path_traversal(self, storage: LocalStorageClient) -> None:
        """key 包含 .. 时应拒绝以防止路径穿越."""
        with pytest.raises(StorageClientError):
            storage.upload_bytes(key="../escape.txt", data=b"evil")

    def test_download_rejects_path_traversal(self, storage: LocalStorageClient) -> None:
        """下载 key 包含 .. 时应拒绝."""
        with pytest.raises(StorageClientError):
            storage.download_bytes("../escape.txt")

    def test_upload_overwrites_existing(
        self, storage: LocalStorageClient, tmp_path: Path
    ) -> None:
        """重复上传同一 key 应覆盖旧内容."""
        storage.upload_bytes(key="doc.txt", data=b"old")
        storage.upload_bytes(key="doc.txt", data=b"new")
        assert (tmp_path / "doc.txt").read_bytes() == b"new"


class TestMinioStorageClient:
    """MinioStorageClient（可选 MinIO 后端）测试."""

    @pytest.fixture
    def storage(self) -> Generator[MinioStorageClient, None, None]:
        """创建带 mock MinIO 客户端的 MinioStorageClient."""
        with patch("app.storage.get_settings") as mock_settings:
            settings = MagicMock()
            settings.minio_endpoint = "localhost:9000"
            settings.minio_access_key = "test"
            settings.minio_secret_key = "test"
            settings.minio_bucket = "financial-agent"
            settings.minio_public_url = "http://minio.example.com"
            mock_settings.return_value = settings

            with patch("app.storage.MinioStorageClient.__init__", return_value=None):
                client = MinioStorageClient()
                client.client = MagicMock()
                client.bucket = "financial-agent"
                client.public_url = "http://minio.example.com"
                yield client

    def test_upload_bytes_success(self, storage: MinioStorageClient) -> None:
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

    def test_download_bytes_success(self, storage: MinioStorageClient) -> None:
        """下载对象内容成功."""
        response = MagicMock()
        response.read.return_value = b"file-content"
        storage.client.get_object.return_value = response

        data = storage.download_bytes("doc.txt")
        assert data == b"file-content"
        storage.client.get_object.assert_called_once_with("financial-agent", "doc.txt")


class TestGetStorageClient:
    """get_storage_client 后端选择与单例测试."""

    def test_returns_local_by_default(self, tmp_path: Path) -> None:
        """默认 storage_backend=local 应返回 LocalStorageClient."""
        with patch("app.storage.get_settings") as mock_settings:
            settings = MagicMock()
            settings.storage_backend = "local"
            settings.storage_local_root = str(tmp_path)
            mock_settings.return_value = settings

            get_storage_client.cache_clear()
            client = get_storage_client()
            assert isinstance(client, LocalStorageClient)

        get_storage_client.cache_clear()

    def test_returns_same_instance(self, tmp_path: Path) -> None:
        """多次调用应返回同一实例（lru_cache 单例）."""
        with patch("app.storage.get_settings") as mock_settings:
            settings = MagicMock()
            settings.storage_backend = "local"
            settings.storage_local_root = str(tmp_path)
            mock_settings.return_value = settings

            get_storage_client.cache_clear()
            client1 = get_storage_client()
            client2 = get_storage_client()
            assert client1 is client2

        get_storage_client.cache_clear()

    def test_returns_base_storage_client(self, tmp_path: Path) -> None:
        """返回的实例应是 BaseStorageClient 子类."""
        with patch("app.storage.get_settings") as mock_settings:
            settings = MagicMock()
            settings.storage_backend = "local"
            settings.storage_local_root = str(tmp_path)
            mock_settings.return_value = settings

            get_storage_client.cache_clear()
            client = get_storage_client()
            assert isinstance(client, BaseStorageClient)

        get_storage_client.cache_clear()
